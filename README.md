# ai-protocol

A small Git-based protocol for multiple AI agents (and humans) sharing a repository across
sessions with no durable chat memory: Git is the single source of truth. This repo is the
protocol's *tooling* -- the `ai-check` and `ai-bootstrap` CLIs and bootstrap templates -- installed once per machine.
Project repos that adopt the protocol contain only data (`AGENTS.md`, `ai/*`), never a copy of
this code.

## Install

```
pipx install git+https://github.com/vu0-studio/ai-protocol
```

If `pipx` itself is missing:

```
python -m pip install --user pipx
python -m pipx ensurepath
```

Open a new shell afterwards (`pipx ensurepath` changes `PATH`) and verify:

```
ai-check --version
```

## Use in a project repo

1. From anywhere inside an existing Git repository, run `ai-bootstrap --agent codex`.
   Review the single local bootstrap commit, fill verified placeholders, and push manually
   if desired. See `BOOTSTRAP.md` for the safety contract.
2. Start every session with `ai-check`. If it reports `BLOCKED`, fix what it lists first.
3. End every session with `ai-check --close`, then commit and write a handoff. See the
   `templates/AGENTS.md` this repo ships for the exact session-start/session-end procedure --
   copy it into the project repo during bootstrap and fill in its `TODO:` markers.

`ai-check` is read-only: it never modifies the repository, its config, or the remote. It only
runs `git` and the standard library -- no dependencies. Remote checks use `git ls-remote`
and `git push --dry-run --no-verify` against the repo's own `origin`; it does not fetch,
run pre-push hooks, or write remote refs. Ahead/behind counts use cached remote-tracking refs.

### Exit status

- `READY` -- everything checked out, including `origin` reachable and (with `--close`) pushed.
- `LOCAL-ONLY` -- structurally fine, but no reachable `origin` (or `--allow-local` accepted this).
  Exit code 1 unless `--allow-local` was supplied to `ai-check`.
- `BLOCKED` -- something in the list is a real problem. Exit code 1.

## Known limitations (deferred)

- `ai-check` must be run from the repo root. It does not `cd` to the toplevel itself.
- Placeholder detection (`"TODO:"`) is a plain substring match anywhere in a file, so prose that
  merely *describes* the marker can trip it. A future version will match an explicit marker only
  at the start of a line.

## Development

```
python -m venv .venv
.venv/Scripts/pip install -e .          # Windows
.venv/bin/pip install -e .              # Linux/macOS
python -m unittest discover tests
```

## Layout

- `src/ai_protocol/check.py` -- the `ai-check` implementation.
- `templates/` -- `AGENTS.md`, `CLAUDE.md`, `STATE.md` starting points for a newly bootstrapped
  project repo. Universal structure is filled in; every project-specific fact is a `TODO:`.
- `src/ai_protocol/bootstrap.py` -- the separate, writing `ai-bootstrap` CLI.
- `src/ai_protocol/templates/AGENTS.md` -- packaged copy of the accepted static template,
  checked against `templates/AGENTS.md` by a regression test.
- `BOOTSTRAP.md` -- bootstrap usage and safety contract.
- `tests/` -- checker regression tests and bootstrap integration/safety tests.
