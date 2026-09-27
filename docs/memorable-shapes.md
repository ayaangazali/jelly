---
title: "Memorable — the output shapes our code parses"
purpose: "Contract for #20 (classifier) and #36 (ingest bridge). Everything here is either observed CLI output or marked as waiting on capture."
updated: "2026-09-27"
---

# Memorable output shapes

The Memorable CLI is closed source and its licence forbids reverse engineering, so the CLI's printed output is the only interface we build on. This doc records that output. Raw captures live in `fixtures/memorable/`.

Pinned version: **`memorable-cli@0.5.30`**.

## Setup (owner only, needs a browser)

```sh
npx memorable-cli@0.5.30 login
npx memorable-cli@0.5.30 enable
scripts/memorable_capture.sh
```

`login` is a device flow: it opens a browser to approve this machine. `enable` is the explicit write consent; nothing is stored before it. The capture script then ingests the three sample traces and saves every output listed below.

We deliberately don't run `install-hooks`. The hooks edit `~/.claude/settings.json` to run recall on every Claude Code prompt. GRADUATE doesn't need them, because the router calls recall itself and the runner ingests sessions itself.

For #20, install the binary once (`npm i -g memorable-cli@0.5.30`) and call `memorable` directly. `npx` adds its own startup time to every call.

## Observed so far (before login)

`fixtures/memorable/status-before-login.txt`:

- The backend is `local (~/.memorable/procedures.jsonl)`.
- Write consent is `unset`, and the CLI says it "fails closed until `memorable enable`".
- **Encryption is `off, no key store on this machine`.** The research said the local store is AES-256-GCM encrypted. In practice it's only encrypted once a key store exists. We still don't parse the file: the licence forbids it, and the CLI output is the supported interface.
- The extraction API is `not configured, run memorable login`. So **`ingest` needs a login**, because it calls Memorable's extraction service.

## Commands we call, and how we parse them

| Command | Called by | Parse |
|---|---|---|
| `memorable recall "<first prompt>" --single` | router classifier (#20), once per session, 500 ms timeout | First line matching `^(?P<score>[0-9.]+)\s+(?P<slug>procedures/\S+)\s+\[(?P<matcher>\w+)\]`. Score ≥ 0.75 means a match; otherwise, or on no line, fall back to the hash |
| `memorable ingest <trace.json>` | ingest bridge (#36), after every passing session | Success or refusal from the output. A refusal includes `allowance_exhausted` (research); log it once and carry on |
| `memorable list --json` | dashboard, optional | JSON array; fields confirmed after capture |
| `memorable chain "<task>" --json` | not on the critical path | Captured for reference |

The recall line format comes from Memorable's docs (`0.86 procedures/ab12cd34-fix-failing-order-tests [lexical]`). `fixtures/memorable/recall-*.txt` will confirm it on this version.

## Trace we send

The contracts §7 shape (the `/v1/extract` body): `{session_id, harness: "opencode", task_description, tool_calls: [{name, input, result}]}`. It uses only the allow-listed input keys (`command`, `file_path`, `path`, `pattern`, `url`, `query`), and results are `{ok}` or `{exit_code}`. The three sample traces in `fixtures/memorable/` follow it:

| File | Task type | Why it's there |
|---|---|---|
| `trace-fix-failing-test-05.json` | fix-failing-test | Includes a failing `pytest` (exit 1) before the fix, then exit 0 |
| `trace-fix-failing-test-07.json` | fix-failing-test | A different path through the same task, including `grep` |
| `trace-update-changelog.json` | update-changelog | A different task, so recall has something to tell apart |

## Waiting on capture (after login and enable)

The capture script fills these; then this section gets the real answers:

- [ ] Recall line format on 0.5.30, and whether a module-03 prompt matches the fix-failing-test procedure
- [ ] Recall latency (`recall-timing.txt`; includes `npx` startup)
- [ ] `list --json` field names
- [ ] What `ingest` prints on success, and the resulting slug
- [ ] Whether `ingest` works offline (expected: no)
