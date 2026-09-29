# Bootstrap checklist

Manual for now (a human or an agent works through this checklist by hand). Automation is
deliberately deferred until a second live repo has been bootstrapped this way -- see the
protocol's decision record for why.

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
7. Point `ai/STATE.md` at that handoff (its "Latest handoffs" section).
8. Stage explicit paths only -- never `git add -A`, so step 2's pre-existing changes can't leak
   into this commit by accident. One commit: `handoff: bootstrap <agent>`.
9. Never create a remote and never push automatically. Print the push command
   (`git push -u origin <branch>`) for a human to run.
10. Run `ai-check`. Report: files created / files that already existed / files modified /
    remaining TODOs / warnings / the commit hash / the push command -- then the `ai-check`
    output verbatim, not paraphrased.
