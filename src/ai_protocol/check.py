#!/usr/bin/env python3
"""Read-only readiness and closing check for the Git-based AI protocol.

    ai-check                # bootstrap / session-start readiness
    ai-check --close        # additionally: clean tree, filled files, HEAD pushed
    add --allow-local to accept a repo with no reachable origin (LOCAL-ONLY) as success
    ai-check --version      # print the installed version and exit

Never modifies the repository, its config or the remote. Uses only git and the standard library.
Exit code 0 = READY (or LOCAL-ONLY with --allow-local); 1 = something to report.

Known limitations (deferred, not fixed here):
- Must be run from the repo root. It does not chdir to the toplevel itself (it discovers the
  toplevel via `git rev-parse --show-toplevel` for reporting, but file checks below are relative
  to the current working directory).
- Placeholder detection ("TODO:") is a plain substring match anywhere in a file, so prose that
  merely describes the mechanism can trip it. Match an explicit start-of-line marker instead,
  in a future version.
"""
import os, re, subprocess, sys

from . import __version__

ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
ENV.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=15")
results = []          # (level, name, detail)  level: PASS FAIL WARN INFO


def git(*args, timeout=25):
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True, env=ENV, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s (waiting for credentials or network?)"
    except FileNotFoundError:
        return 127, "git not found on PATH"


def rec(level, name, detail=""):
    results.append((level, name, detail))


def run_checks():
    close = "--close" in sys.argv
    allow_local = "--allow-local" in sys.argv
    rc, out = git("rev-parse", "--is-inside-work-tree")
    if rc != 0 or out != "true":
        rec("FAIL", "git repository", out or "not inside a Git work tree")
        return report(close)
    rc, top = git("rev-parse", "--show-toplevel")
    rec("PASS", "git repository", top)
    rc, branch = git("symbolic-ref", "--short", "-q", "HEAD")
    if rc != 0:
        rec("FAIL", "current branch", "detached HEAD: create or switch to a branch first")
        branch = None
    else:
        rec("PASS", "current branch", branch)
    for key in ("user.name", "user.email"):
        rc, val = git("config", key)
        rec("PASS" if rc == 0 and val else "FAIL", f"git {key}", val or "not set: commits will fail or be anonymous")

    # remote
    rc, url = git("remote", "get-url", "origin")
    remote_ok = False
    if rc != 0:
        rec("WARN", "origin remote", "no 'origin': protocol works locally but NOT backed up (LOCAL-ONLY)")
    else:
        rec("PASS", "origin remote", url)
        if re.match(r"^(file://|/|\.{1,2}/|[A-Za-z]:[\\/])", url):
            rec("WARN", "remote is a local path", "make sure it is on a different disk, otherwise it is not a backup")
        rc, out = git("ls-remote", "--heads", "origin")
        rec("PASS" if rc == 0 else "FAIL", "remote read access (ls-remote)", "" if rc == 0 else out[:300])
        remote_ok = rc == 0
        if remote_ok:
            rc, out = git("fetch", "origin")
            rec("PASS" if rc == 0 else "FAIL", "git fetch origin", "" if rc == 0 else out[:300])
            if branch:
                rc, out = git("push", "--dry-run", "origin", f"HEAD:refs/heads/{branch}")
                rec("PASS" if rc == 0 else "FAIL", "push dry-run (auth and fast-forward only)",
                    "does not prove branch protection or server hooks" if rc == 0 else out[:300])

    # ahead / behind
    if branch and remote_ok:
        rc, out = git("rev-parse", "--verify", "-q", f"origin/{branch}")
        if rc == 0:
            rc, cnt = git("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
            behind, ahead = (cnt.split() + ["?", "?"])[:2]
            lvl = "PASS" if (behind, ahead) == ("0", "0") else "WARN"
            rec(lvl, "vs origin/" + branch, f"behind {behind}, ahead {ahead}")
        else:
            rec("WARN", "vs origin/" + branch, "branch not on origin yet: first push needs -u")

    # tree
    rc, porcelain = git("status", "--porcelain")
    dirty = bool(porcelain)
    rec("FAIL" if (dirty and close) else ("WARN" if dirty else "PASS"), "working tree",
        f"{len(porcelain.splitlines())} changed/untracked path(s)" if dirty else "clean")

    # files
    for f in ("AGENTS.md", "CLAUDE.md", "ai/STATE.md", ".gitignore"):
        rec("PASS" if os.path.isfile(f) else "FAIL", f"file {f}", "" if os.path.isfile(f) else "missing")
    if os.path.isfile("CLAUDE.md"):
        first = open("CLAUDE.md", encoding="utf-8").readline().strip()
        rec("PASS" if first == "@AGENTS.md" else "FAIL", "CLAUDE.md imports AGENTS.md",
            "" if first == "@AGENTS.md" else f"first line is {first!r}, expected '@AGENTS.md'")

    # handoffs: one immutable file per session in ai/handoffs/, never a single overwritten file
    # (see AGENT-WORKFLOW-PROTOCOL.md 0.5 and template 4.4 - this replaces the old single
    # ai/HANDOFF.md check, which does not match the adopted per-session file format)
    handoffs_dir = "ai/handoffs"
    handoff_files = sorted(f for f in os.listdir(handoffs_dir) if f.endswith(".md")) if os.path.isdir(handoffs_dir) else []
    rec("PASS" if handoff_files else "FAIL", "dir ai/handoffs/",
        f"{len(handoff_files)} file(s), latest {handoff_files[-1]}" if handoff_files
        else "missing or empty: no session has recorded a handoff yet")
    latest_handoff = os.path.join(handoffs_dir, handoff_files[-1]) if handoff_files else None

    # TODO: placeholders. AGENTS.md is checked in every mode but only blocks at close:
    # a freshly bootstrapped repo is "structurally correct, honestly incomplete" and must not
    # read as BLOCKED at session start. STATE and the latest handoff are checked at close only.
    for f in ("AGENTS.md",) + (("ai/STATE.md",) if close else ()) + ((latest_handoff,) if close and latest_handoff else ()):
        if f and os.path.isfile(f) and "TODO:" in open(f, encoding="utf-8").read():
            rec("FAIL" if close else "WARN", f"{f} placeholders", "still contains 'TODO:' - fill it in")

    # secrets in tracked files (names only)
    rc, files = git("ls-files")
    bad = [p for p in files.splitlines() if re.search(r"(^|/)(\.env(\..*)?|id_rsa|id_ed25519)$|\.(pem|key|p12|pfx)$", p)]
    rec("FAIL" if bad else "PASS", "secret-like tracked files", ", ".join(bad[:5]))

    # handoff drift: compare the newest handoff's head_sha (front matter, template 4.4) with HEAD.
    # Note: head_sha in the template is "HEAD of the task branch when the handoff was generated",
    # i.e. BEFORE the handoff file itself is committed (its own sha isn't known yet). So at
    # closing time HEAD is normally exactly 1 commit ahead of head_sha - that extra commit is the
    # "handoff: <task> <agent>" commit that adds the handoff file. Do not require sha == HEAD.
    if latest_handoff:
        text = open(latest_handoff, encoding="utf-8").read()
        m = re.search(r"^head_sha:\s*([0-9a-f]{7,40})", text, re.MULTILINE)
        if not m:
            m = re.search(r"^base_sha:\s*([0-9a-f]{7,40})", text, re.MULTILINE)
        if m:
            sha = m.group(1)
            rc, _ = git("merge-base", "--is-ancestor", sha, "HEAD")
            if rc == 0:
                rc, n = git("rev-list", "--count", f"{sha}..HEAD")
                rec("INFO", "handoff drift", f"{latest_handoff}: recorded sha {sha[:12]} is an ancestor of HEAD; "
                    f"{n} commit(s) since (normally 1: the handoff's own commit)")
            else:
                rec("FAIL" if close else "WARN", "handoff drift", f"{latest_handoff}: {sha} is not an ancestor of HEAD or unknown")
        else:
            rec("WARN", "handoff drift", f"{latest_handoff}: no 'head_sha:' or 'base_sha:' front-matter field found")

        if close:
            # closing check: HEAD itself must be the commit that records this handoff
            rc, subject = git("log", "-1", "--format=%s", "HEAD")
            rc2, changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
            touched = latest_handoff.replace(os.sep, "/") in changed.splitlines()
            rec("PASS" if subject.startswith("handoff:") else "FAIL", "HEAD commit is a handoff commit",
                "" if subject.startswith("handoff:") else f"HEAD subject is {subject!r}, expected to start with 'handoff:'")
            rec("PASS" if touched else "FAIL", "latest handoff committed at HEAD",
                "" if touched else f"{latest_handoff} is not part of the HEAD commit: commit it as 'handoff: <task-id> <agent>'")
    elif close:
        rec("FAIL", "handoff drift", "no file in ai/handoffs/ to check")

    # closing: HEAD must be on origin
    if close and branch:
        if not remote_ok and allow_local:
            rec("WARN", "HEAD pushed", "skipped: no reachable origin, LOCAL-ONLY accepted via --allow-local "
                "(NOT recoverable without this disk)")
        elif not remote_ok:
            rec("FAIL", "HEAD pushed", "no reachable origin: NOT recoverable without this disk")
        else:
            rc, head = git("rev-parse", "HEAD")
            rc, line = git("ls-remote", "origin", f"refs/heads/{branch}")
            remote_sha = line.split()[0] if rc == 0 and line else ""
            rec("PASS" if remote_sha == head else "FAIL", "HEAD pushed",
                f"HEAD {head[:12]} == origin/{branch}" if remote_sha == head else f"HEAD {head[:12]} vs origin {remote_sha[:12] or 'absent'}")
    return report(close, allow_local, remote_ok)


def report(close, allow_local=False, remote_ok=False):
    fails = [r for r in results if r[0] == "FAIL"]
    for lvl, name, detail in results:
        print(f"[{lvl:4}] {name}" + (f": {detail}" if detail else ""))
    has_origin = any(n == "origin remote" and l == "PASS" for l, n, _ in results)
    if fails:
        status = "BLOCKED"
    elif not has_origin:
        status = "LOCAL-ONLY"
    else:
        status = "READY"
    print(f"\nSTATUS: {status}" + ("  (close check)" if close else ""))
    rc, head = git("rev-parse", "--short", "HEAD")
    if rc == 0:
        print(f"HEAD: {head}")
    return 0 if status == "READY" or (status == "LOCAL-ONLY" and allow_local) else 1


def cli():
    """Entry point (console script `ai-check`)."""
    if "--version" in sys.argv:
        print(f"ai-check {__version__}")
        return 0
    print(f"ai-check {__version__}")
    return run_checks()


def main():
    sys.exit(cli())


if __name__ == "__main__":
    main()
