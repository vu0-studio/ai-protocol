@AGENTS.md

# Claude Code specifics
- TODO: note plan-mode thresholds, hook status (`.claude/settings.json`), and any other
  Claude-Code-specific behavior for this project.
- Auto memory is a private cache, not a source of truth: put anything worth keeping in the repo.
- Run `ai-check` yourself at session start and `ai-check --close` at session end unless hooks are
  confirmed to enforce this automatically.
