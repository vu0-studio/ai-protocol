# ai-protocol

A small Git-based protocol for multiple AI agents (and humans) sharing a repository across
sessions with no durable chat memory: Git is the single source of truth. This repo is the
protocol's *tooling* -- the `ai-check` CLI and bootstrap templates -- installed once per machine.
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

1. Bootstrap the repo once by hand, following `BOOTSTRAP.md` in this repo (a human or an agent
   works through it as a checklist; nothing here automates it yet).
2. Start every session with `ai-check`. If it reports `BLOCKED`, fix what it lists first.
3. End every session with `ai-check --close`, then commit and write a handoff. See the
   `templates/AGENTS.md` this repo ships for the exact session-start/session-end procedure --
   copy it into the project repo during bootstrap and fill in its `TODO:` markers.

`ai-check` is read-only: it never modifies the repository, its config, or the remote. It only
runs `git` and the standard library -- no dependencies, no network calls beyond `git fetch`/
`git ls-remote` against the repo's own `origin`.

### Exit status

- `READY` -- everything checked out, including `origin` reachable and (with `--close`) pushed.
- `LOCAL-ONLY` -- structurally fine, but no reachable `origin` (or `--allow-local` accepted this).
  Exit code 0.
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
- `BOOTSTRAP.md` -- the manual bootstrap checklist.
- `tests/` -- regression tests for `ai-check`, run against the installed module.
