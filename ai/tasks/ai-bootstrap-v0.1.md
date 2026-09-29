# ai-bootstrap v0.1

Status: complete; implemented, tested, and committed locally. No push authorized.

User-approved scope: sibling CLI, stdlib only, mechanical protocol scaffolding, isolated
bootstrap commit, no push. Preserve dirty bytes and index entries. Existing checker
remains read-only. No project setup/test/lint/build execution by bootstrap.

Review fixes delivered in package 0.2.0: LOCAL-ONLY exits 0; writing repairs record a new
handoff; one packaged AGENTS template; branch-before-bootstrap and hook-bypass documentation.

Validation: 32 tests pass. Wheel build/install and installed console-script smoke tests
with and without origin pass (exit 0 for READY and LOCAL-ONLY). Publication scan passed.
