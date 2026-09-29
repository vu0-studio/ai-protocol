# Agent instructions
Git is the durable source of truth. Run ai-check at session start and ai-check --close at session end.
Read ai/STATE.md, the relevant task, and the newest handoff before editing.
Work on a task branch; preserve user changes. Never push without explicit authorization.
Use the standard library; ask before adding dependencies or changing architecture.
Tests: python -m unittest discover tests (with src on PYTHONPATH or the package installed).
Commit verified work and record an immutable UTC handoff. Never invent test results.
