# STATE
<!-- Hand-maintained -->

ai-bootstrap v0.1 is implemented on agent/codex/ai-bootstrap-v0.1.
The tooling package now provides ai-check and ai-bootstrap using the standard library.

## Active tasks
ai-bootstrap-v0.1: complete, tested, committed locally; no push authorized.

## Commands
Test: .venv/Scripts/python.exe -m unittest discover tests -v
Build: .venv/Scripts/python.exe -m pip wheel --no-deps --wheel-dir .venv/wheels .
No runtime dependencies added. Lint is not configured.

## Verification
28 tests passed. Installed-wheel console script bootstrapped an unborn scratch repository
with one commit and returned the faithful LOCAL-ONLY checker result (exit 1).
Linux execution not verified.

## Open questions
None. No push authorized.

## Latest handoff
ai/handoffs/20260929T123045Z-codex-ai-bootstrap-v0.1.md
