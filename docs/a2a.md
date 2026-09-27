# A2A notes (#142)

Agents on the same task type share what worked. After a **verified** pass the runner writes one short note for the task type (the session, the files it changed, the test command that went green). The next run of that task type gets the note prepended to its prompt under `## Notes from other agents`. A failing run writes nothing. An a2a error never fails a run.

Code: [`graduate/a2a.py`](../graduate/a2a.py) (`get(task_type)`, `put(task_type, text, session_id)`), called from `graduate.runner.run`. Tests: [`tests/test_a2a.py`](../tests/test_a2a.py).

## Backends

| Backend | When | Where the note lives |
|---|---|---|
| GBrain | `gbrain` (or `$GBRAIN_BIN`, as in `graduate/gbrain.py`) runs and exits 0 | page `a2a-<task_type>` in the local brain: `gbrain put a2a-<task_type> --force` / `gbrain get a2a-<task_type>` |
| Shared notes file (GBrain not installed) | GBrain is missing or fails | `a2a/<task_type>.md` in the working directory (gitignored) |

Trace (`trace.jsonl`): `Runner → GBrain`, nodes `runner` `gbrain`, edge `a2a-read` or `a2a-write`, with the session id. The `result` names the backend, e.g. `read 142 chars · GBrain` or `wrote 142 chars · shared notes file (GBrain not installed)`. A read event is only emitted when a note was found.

## Install GBrain locally (bun, PGLite, no cloud account)

`bun install -g github:garrytan/gbrain` fails on this host (`Couldn't find patch file: 'patches/postgres@3.4.9.patch'`), so install from a clone, as GBrain's `INSTALL_FOR_AGENTS.md` falls back to:

```sh
git clone --depth 1 https://github.com/garrytan/gbrain.git ~/.local/share/gbrain   # tested at e78f1c3 (v0.59.0.0)
cd ~/.local/share/gbrain && bun install && bun link      # puts `gbrain` in ~/.bun/bin
gbrain init --pglite --no-embedding                      # keyless local brain in ~/.gbrain
printf 'round trip\n' | gbrain put a2a-smoke --force && gbrain get a2a-smoke
```

`gbrain` is a `#!/usr/bin/env bun` script, so `~/.bun/bin` must be on `PATH`. `GBRAIN_HOME=<dir>` puts the brain in `<dir>/.gbrain` instead of `~/.gbrain` (handy for a scratch brain). `put` needs `--force` to overwrite an existing page.
