"""Mechanical protocol bootstrap; the sibling checker remains read-only."""
import argparse
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

from . import __version__

IGNORE = ("ai/logs/", ".claude/settings.local.json", "CLAUDE.local.md")


class Stop(RuntimeError):
    pass


def git(*args, required=True):
    literal = [] if args[0] == "check-ignore" else ["--literal-pathspecs"]
    p = subprocess.run(["git", *literal, *args], capture_output=True,
                       env=dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0"), timeout=60)
    if required and p.returncode:
        raise Stop(p.stderr.decode(errors="replace").strip() or "git failed")
    return p


def output(*args, required=True):
    return git(*args, required=required).stdout.decode(errors="surrogateescape").strip()


def dirty():
    fields = git("status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.split(b"\0")
    paths = set()
    while fields:
        row = fields.pop(0)
        if not row:
            continue
        paths.add(os.fsdecode(row[3:]))
        if b"R" in row[:2] or b"C" in row[:2]:
            paths.add(os.fsdecode(fields.pop(0)))
    return paths


def fingerprint(path):
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return None
    s = p.lstat()
    if stat.S_ISLNK(s.st_mode):
        data = os.fsencode(os.readlink(p))
    elif p.is_file():
        data = p.read_bytes()
    else:
        raise Stop("Cannot safely snapshot dirty directory/submodule: " + path)
    return s.st_mode, hashlib.sha256(data).hexdigest()


def index_entries():
    return {os.fsdecode(row.split(b"\t", 1)[1]): row
            for row in git("ls-files", "--stage", "-z").stdout.split(b"\0") if row}


def safe_path(name):
    p = Path(name)
    for part in [p, *p.parents]:
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise Stop("Refusing symlink/junction protocol path: " + str(part))
    for parent in p.parents:
        if parent.exists() and not parent.is_dir():
            raise Stop("Expected directory: " + str(parent))
    if p.exists() and not p.is_file():
        raise Stop("Expected regular file: " + name)


def run(agent):
    root = output("rev-parse", "--show-toplevel")
    os.chdir(root)
    branch = output("symbolic-ref", "--short", "-q", "HEAD", required=False)
    if not branch:
        raise Stop("Detached HEAD: bootstrap requires a branch")
    for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply"):
        if Path(output("rev-parse", "--git-path", marker)).exists():
            raise Stop("Merge/rebase in progress: " + marker)
    for key in ("user.name", "user.email"):
        if not output("config", key, required=False):
            raise Stop("Missing git " + key)
    before = dirty()
    snapshots = {name: fingerprint(name) for name in before}
    old_index = index_entries()
    base = output("rev-parse", "--verify", "HEAD", required=False) or "none"
    origin = output("remote", "get-url", "origin", required=False) or "LOCAL-ONLY"
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    handoff = "ai/handoffs/" + now.strftime("%Y%m%dT%H%M%SZ") + "-" + agent + "-bootstrap.md"
    plan, originals, modifications, present, warnings = {}, {}, {}, [], []

    def inspect(name):
        safe_path(name)
        data = Path(name).read_bytes() if Path(name).exists() else None
        originals[name] = data
        if data is not None:
            present.append(name)
        return data

    def change(name, content, description):
        if any(name == p or name.startswith(p + "/") or p.startswith(name + "/") for p in before):
            raise Stop("Pre-existing user change needs protocol repair; left untouched: " + name)
        if originals[name] is not None and git("ls-files", "--error-unmatch", "--", name, required=False).returncode:
            raise Stop("Pre-existing untracked/ignored protocol file needs repair; left untouched: " + name)
        flags = git("ls-files", "-v", "--", name).stdout
        if flags and (flags[:1].islower() or flags[:1] == b"S"):
            raise Stop("Cannot safely modify assume-unchanged/skip-worktree path: " + name)
        ignored = git("check-ignore", "-q", "--", name, required=False)
        if ignored.returncode not in (0, 1):
            raise Stop("Cannot determine ignore status: " + name)
        if ignored.returncode == 0:
            raise Stop("Protocol path is ignored; resolve ignore rule before bootstrap: " + name)
        plan[name] = content
        if originals[name] is not None:
            modifications[name] = description

    agents = inspect("AGENTS.md")
    if agents is None:
        template = resources.files("ai_protocol").joinpath("templates/AGENTS.md").read_bytes()
        change("AGENTS.md", template.replace(b"\r\n", b"\n"), "created accepted template")
    elif any(section not in agents for section in
             (b"Start of every session", b"Rules", b"End of every session")):
        warnings.append("AGENTS.md may be missing cross-AI protocol sections; preserved unchanged")
    claude = inspect("CLAUDE.md")
    if claude is None:
        change("CLAUDE.md", b"@AGENTS.md\n", "created import")
    elif not claude.splitlines() or claude.splitlines()[0] != b"@AGENTS.md":
        change("CLAUDE.md", b"@AGENTS.md\n" + claude, "prepended exactly @AGENTS.md and LF; original bytes preserved")
    state = inspect("ai/STATE.md")
    keep = inspect("ai/tasks/.gitkeep")
    if keep is None:
        change("ai/tasks/.gitkeep", b"", "created placeholder")
    ignore = inspect(".gitignore")
    missing = [entry for entry in IGNORE if entry.encode() not in (ignore or b"").splitlines()]
    if ignore is None or missing:
        data = ignore or b""
        if data and not data.endswith(b"\n"):
            data += b"\n"
        change(".gitignore", data + "".join(s + "\n" for s in missing).encode(),
               "appended missing entries: " + ", ".join(missing))
    inspect(".gitattributes")  # Inspect only; never write.
    safe_path("ai/handoffs/.bootstrap-path-check")
    handoffs = sorted(p for p in Path("ai/handoffs").glob("*.md") if p.is_file())
    for existing_handoff in handoffs:
        safe_path(existing_handoff.as_posix())
    # Every writing run records its own immutable handoff, including repairs.
    new_handoff = bool(plan) or state is None or not handoffs
    if new_handoff:
        while Path(handoff).exists():
            time.sleep(0.05)
            now = datetime.now(timezone.utc)
            timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            handoff = "ai/handoffs/" + now.strftime("%Y%m%dT%H%M%SZ") + "-" + agent + "-bootstrap.md"
        inspect(handoff)
        change(handoff, b"", "created bootstrap handoff")
    else:
        handoff = handoffs[-1].as_posix()
    if state is None:
        change("ai/STATE.md", (
            "# STATE\n<!-- Hand-maintained until agent tooling renders this automatically -->\n\n"
            f"Last updated: {timestamp} by {agent} (bootstrap)\n\n"
            "## What this project is\nTODO: not yet described\n\n"
            "## Active tasks\nNone recorded.\n\n"
            "## Commands\nSetup: TODO: not verified\nTest: TODO: not verified\n"
            "Lint: TODO: not verified\nBuild: TODO: not verified\n\n"
            "## Open questions\n- Project description not yet verified.\n"
            "- Setup/test/lint/build commands not yet verified.\n\n"
            f"## Latest handoff\n{handoff}\n").encode(), "created honest bootstrap state")
    created = [name for name in plan if originals[name] is None]
    untouched = [name for name in present if name not in plan]
    todos = []
    for name in ("AGENTS.md", "ai/STATE.md"):
        data = plan.get(name, originals[name]) or b""
        todos.extend(f"{name}:{n}: {line}" for n, line in
                     enumerate(data.decode(errors="replace").splitlines(), 1) if "TODO:" in line)
    if new_handoff:
        content = (
            f"---\ntask: bootstrap\nagent: {agent}\nstarted: {timestamp}\nended: {timestamp}\n"
            f"branch: {json.dumps(branch)}\nbase_sha: {base}\nhead_sha: {base}\n"
            "tree: bootstrap-owned paths only; pre-existing changes preserved\n"
            "evidence: bootstrap snapshot verification\n---\n"
            "Bootstrap exception: this single mechanical bootstrap commit is permitted on the current branch, including the default branch.\n"
        )
        for label, values in (("Files created", created), ("Files already present", present),
                              ("Files modified by bootstrap", [f"{k}: {v}" for k, v in modifications.items()]),
                              ("Pre-existing dirty paths", sorted(before)), ("TODOs remaining", todos),
                              ("Remote state", [origin]), ("Warnings / blockers", warnings)):
            content += "\n## " + label + "\n" + ("\n".join("- " + json.dumps(v, ensure_ascii=True) for v in values) or "None.") + "\n"
        plan[handoff] = content.encode()

    def verify(written=False):
        if any(fingerprint(p) != value for p, value in snapshots.items()):
            raise Stop("Pre-existing user path changed; STOP before commit")
        current_index = index_entries()
        if {p: v for p, v in current_index.items() if p not in plan} != {
                p: v for p, v in old_index.items() if p not in plan}:
            raise Stop("Unrelated index entries changed; STOP before commit")
        if dirty() - set(plan) != before - set(plan):
            raise Stop("Working tree changed concurrently; STOP before commit")
        for name, data in (plan if written else {p: originals[p] for p in plan}).items():
            safe_path(name)
            current = Path(name).read_bytes() if Path(name).exists() else None
            if current != data:
                raise Stop("Protocol path changed concurrently; STOP before commit: " + name)

    commit = "no commit needed"
    if plan:
        verify()
        for name, data in plan.items():
            p = Path(name)
            p.parent.mkdir(parents=True, exist_ok=True)
            if originals[name] is None:
                with p.open("xb") as f:
                    f.write(data)
            else:
                p.write_bytes(data)
        verify(written=True)
        # An explicit path list plus --only keeps already-staged user changes out.
        git("add", "--", *plan)
        verify(written=True)
        hooks = output("rev-parse", "--git-path", "ai-bootstrap-no-hooks")
        if Path(hooks).exists():
            raise Stop("Reserved no-hooks path exists; STOP before commit")
        git("-c", "core.hooksPath=" + str(Path(hooks).absolute()),
            "commit", "--only", "-m", "handoff: bootstrap " + agent, "--", *plan)
        commit = output("rev-parse", "HEAD")
        verify(written=True)
        print("Bootstrap structure created successfully.")
    else:
        verify()
        print("already structurally bootstrapped")
    report = {
        "repo root": root, "branch": branch, "files created": created,
        "files already present and untouched": untouched, "files modified": modifications,
        "remaining TODOs": todos, "pre-existing dirty paths": sorted(before),
        "pre-existing paths remained untouched": True, "handoff filename": handoff,
        "bootstrap commit SHA": commit, "origin status": origin, "warnings": warnings,
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    if origin != "LOCAL-ONLY":
        print("Manual push after review: git push -u origin " + branch)
    print("Next action: review bootstrap; push manually if desired; fill verified TODOs.")
    print("\n--- ai-check output ---", flush=True)
    result = subprocess.run([sys.executable, "-m", "ai_protocol.check", "--allow-local"])
    print("ai-check exit code: " + str(result.returncode))
    return result.returncode


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, help="agent identifier for commit and handoff")
    parser.add_argument("--version", action="version", version="ai-bootstrap " + __version__)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.agent):
        parser.error("--agent must contain lowercase letters, digits, and single separating hyphens")
    previous = Path.cwd()
    try:
        return run(args.agent)
    except (Stop, OSError, subprocess.SubprocessError) as exc:
        print("ai-bootstrap: STOP: " + str(exc), file=sys.stderr)
        return 1
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    sys.exit(cli())
