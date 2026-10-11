# STATE
<!-- Hand-maintained -->

Session ordering and task-scoped verification guidance are corrected in the packaged template and README. Package version remains 0.2.0.
The tooling package now provides ai-check and ai-bootstrap using the standard library.

## Active tasks
standards-fix: documentation and template corrections complete; branch push and fast-forward of master authorized.

## Commands
Test: .venv/Scripts/python.exe -m unittest discover tests -v
Build: .venv/Scripts/python.exe -m pip wheel --no-deps --wheel-dir .venv/wheels .
No runtime dependencies added. Lint is not configured.

## Verification
Latest validation: python -m unittest discover tests with src on PYTHONPATH: 32 tests passed in 46.381s. The initial run without PYTHONPATH failed because the package was not importable. No test expectations required changes. git diff --check passed. Installed tools still ship the old template until reinstalled; no reinstall performed.

Historical release validation: 32 tests passed in 36.711s. Wheel 0.2.0 built and installed. Both console scripts report 0.2.0.
Installed-wheel scratch smoke: no origin = LOCAL-ONLY, exit 0; local bare origin = READY, exit 0.
Each scratch run created one commit and no remote refs. STOP and BLOCKED return 1 in tests.
Writing repair runs create a new immutable handoff; no-change reruns remain idempotent.
Working tree, reachable historical trees, and commit messages passed the publication scan.
Linux execution not verified.

## Open questions
None. The PO approved use of existing master instead of absent main.

## Latest handoff
ai/handoffs/20261011T151903Z-codex-standards-fix.md
