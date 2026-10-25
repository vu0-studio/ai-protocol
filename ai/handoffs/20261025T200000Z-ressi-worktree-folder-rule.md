---
task: worktree-folder-rule-20261025
agent: claude-code (Ressi role, Sonnet 5.5)
started: 2026-10-25
ended: 20261025T200000Z
base_sha: 387f9e4
head_sha: 387f9e4
branch: agent/ressi/worktree-folder-rule-20261025
tree: clean after this single commit (rule, state and handoff together); worktree under E:\Git\vu0-studio\_worktrees
evidence: git diff of src/ai_protocol/templates/AGENTS.md
---

## What I did
Added the PO rule "every agent worktree only under E:\Git\vu0-studio\_worktrees\<repo>--<task-id>, removed with git worktree remove after merge and push, branches kept, _worktrees never committed" to src/ai_protocol/templates/AGENTS.md. No code changed.

## Decisions made
head_sha equals base_sha because the change and this handoff are one commit. The rule text asks for an absolute path in git worktree add (a relative path is resolved against the repo). Existing worktrees are not moved.

## Not verified / known failures
Nothing was merged. ai-protocol: 4 tests of test_check.py fail on the base commit as well (test_agents_todo_*, test_no_origin_close_*), unrelated to this change.

## Open questions
Update the code and docs listed in kisa-env docs/reports/worktree-folder-rule-20261025/PATHS-TO-CHANGE.md (gitops.worktree_for, scheduler.md, INSTALL-MORNING.md, STATION-MAP.md, tests) in a separate task.

## Next action
PO merges the four rule branches.
