# Bootstrap v0.1

The second live bootstrap met the agreed automation trigger. Install the same package with
`pipx install git+https://github.com/vu0-studio/ai-protocol`, then run:

```
ai-bootstrap --agent codex
```

Run from any directory inside an existing Git work tree. The agent identifier must use
lowercase letters/digits, optionally separated by single hyphens. No repository is initialized.
Detached HEAD, an active merge/rebase, and missing Git identity cause refusal before writes.

The command plans changes first, snapshots dirty file bytes and index entries, writes only
eligible protocol files, stages explicit paths, and makes one `handoff: bootstrap <agent>`
commit using `git commit --only`. Already-staged user changes remain staged and excluded.
Existing dirty/ignored protocol files that need repair cause refusal before writes. Dirty
submodules/directories, symlink/junction protocol paths, and assume-unchanged/skip-worktree
files that need repair are conservatively refused. A detected concurrent change stops the
commit; bootstrap does not reset, clean, stash, or roll back user work. If Git fails after
writes, inspect the reported error and working tree before retrying. Avoid concurrent writers.
Repository commit hooks are bypassed for this mechanical commit; none are installed.

New files use LF. Existing AGENTS/STATE and all .gitattributes content remain untouched.
Existing CLAUDE content is preserved byte-for-byte after the prepended import. Existing
handoffs are reused when creating a missing STATE. A repeat run makes no empty commit.
No dependencies, setup/test/lint/build execution, remote changes, or automatic push.

Finally the existing checker runs as a separate process, its output is inherited verbatim,
and its exit code is returned. Structural success can therefore still exit 1 for LOCAL-ONLY
or BLOCKED. Read both the bootstrap report and the checker result. Review the local commit,
push manually if desired, then fill placeholders only with verified facts.

## Mechanical checklist

Applying this to a repo means: create the minimum structure `ai-check` needs to report
something other than "no protocol here" (see README.md), without guessing any repo-specific
fact it hasn't actually verified.

1. `cd` to `git rev-parse --show-toplevel`. Stop if: not a git repo, detached HEAD, no
   `user.name`/`user.email` configured, or a merge/rebase is in progress.
2. Note any pre-existing uncommitted changes. Never include them in the bootstrap commit --
   they are somebody else's in-progress work.
3. Create only what is missing: `AGENTS.md`, `CLAUDE.md`, `ai/STATE.md`, `ai/tasks/.gitkeep`,
   `ai/handoffs/`. Never overwrite an existing file.
   - Existing `CLAUDE.md` without `@AGENTS.md` on line 1: prepend that one line only, change
     nothing else.
   - Existing `AGENTS.md`: leave it alone, warn that bootstrap skipped it.
4. Repo-specific facts in `AGENTS.md` (the five-line project description, setup/test/lint
   commands) stay `TODO:` unless verified by actually running them. Bootstrap itself does not
   run setup or test commands -- it creates a structurally correct, honestly incomplete file.
5. Append the protocol's `.gitignore` lines if not already present: `ai/logs/`,
   `.claude/settings.local.json`, `CLAUDE.local.md`. Do not add or change `.gitattributes`.
6. Write the first handoff, `ai/handoffs/<UTC>-<agent>-bootstrap.md` (`YYYYMMDDTHHMMSSZ` for
   `<UTC>`): what was created, what already existed, remaining TODOs, any blockers. `base_sha`
   is `HEAD` before bootstrap ran, or the literal string `none` in a brand-new empty repo. This
   handoff documents what bootstrap did, not a review of the project.
7. If creating `ai/STATE.md`, point it at that handoff. Preserve an existing STATE unchanged.
8. Stage explicit paths only -- never `git add -A`, so step 2's pre-existing changes can't leak
   into this commit by accident. One commit: `handoff: bootstrap <agent>`.
9. Never create a remote and never push automatically. Print the push command
   (`git push -u origin <branch>`) for a human to run.
10. Run `ai-check`. Report: files created / files that already existed / files modified /
    remaining TODOs / warnings / the commit hash / the push command -- then the `ai-check`
    output verbatim, not paraphrased.
