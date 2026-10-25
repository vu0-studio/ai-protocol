# AGENTS.md

Applies to every agent (Claude Code, Codex, Qwen, others) and to humans.
Git is the source of truth. Chat memory is not. If it matters later, it is in the repo.

## 1. Start of every session (in this order)
1. Run `ai-check`. If `ai-check` is missing: `pipx install git+https://github.com/vu0-studio/ai-protocol`.
   If it reports BLOCKED, fix what it lists before doing anything else.
2. Read `ai/STATE.md`, your task file in `ai/tasks/`, and the newest file in `ai/handoffs/`.
3. Compare the handoff's `head_sha` (or `base_sha`) with `git rev-parse HEAD`. If they differ, run
   `git log --stat <sha>..HEAD` before trusting anything written before.
4. Do not trust a claim you can verify in under a minute. Re-run the verified commands listed in `ai/STATE.md` that your task can affect.
5. Work only on your task's branch/worktree. Never commit to `main`/`master` directly unless the
   task is explicitly small, low-risk, and already approved by the PO (state this in the handoff).

## 2. Project in five lines
TODO: replace with this project's actual five-line description -- what it is, its main
components/entry points, the target platform, and what is explicitly out of scope.

## 3. Commands
- Setup: TODO: verify against the actual repo (setup scripts, package manifests) and fill in the
  exact command. Do not guess.
- Test: TODO: verify by actually running the test suite and fill in exactly what you ran and its
  result (count, pass/fail).
- Lint/type: TODO: verify whether a linter or type-checker is configured; if none, say so
  explicitly here, don't invent one.
- Readiness / closing gate: `ai-check` at session start, `ai-check --close` at session end.

## 4. Rules
- One task, one branch `agent/<agent>/<task-id>`, one worktree when working in parallel; a single
  active agent may work directly on a feature branch if there is no parallelism risk.
- Worktrees: Every agent worktree is created ONLY under `E:\Git\_work\worktrees\<repo>--<task-id>`, never next to the repo (give `git worktree add` an absolute path). The folder `E:\Git\_work` is not a Git repo and is never committed. After the task branch is merged and pushed, remove the worktree with `git worktree remove <path>`; branches are not deleted. Worktrees that already exist elsewhere are not moved by this rule.
- Commit at every verified checkpoint. Prefix unfinished work with `wip:`.
- Never end a session with a dirty tree. If the work is not ready, commit it as `wip:`.
- Never write test results by hand. Run the actual check and cite real output.
- Architecture decisions: create a `proposed` ADR in `docs/decisions/` (if this project uses ADRs).
  Only the PO sets `accepted`.
- If you do not know or did not verify something, write "not verified". Never invent quotes,
  counts, paths.
- `ai/STATE.md` is hand-maintained until a `render-state` tool exists for this project -- update
  it by hand at session end until then.
- Do not edit accepted ADRs (supersede them instead).
- Do not read or write secrets. Do not touch files outside the repository.
- Ask the PO before: adding dependencies, changing the architecture, deleting data, force-pushing.

## 5. End of every session
1. Update `ai/STATE.md`.
2. Commit the work.
3. Write a new immutable file `ai/handoffs/<UTC>-<agent>-<task>.md` (front matter: task, agent,
   started, ended, base_sha, head_sha, branch, tree, evidence) with sections "What I did",
   "Decisions made", "Not verified / known failures", "Open questions", "Next action" (exactly one).
4. Commit it as `handoff: <task-id> <agent>`; it must be the last commit.
5. Push the branch.
6. Run `ai-check --close`; it must report READY. Fix what it lists and repeat.

## 6. Where things are
- Rules: this file. Decisions: `docs/decisions/` (if this project uses ADRs).
- Current state: `ai/STATE.md`. Tasks: `ai/tasks/`. History: `ai/handoffs/`.

## 7. Gotchas (each with date and how to verify)
- TODO: record project-specific gotchas here as they are discovered, each dated and with a way
  to verify it still applies.
