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

## Before login

`fixtures/memorable/status-before-login.txt`:

- The backend is `local (~/.memorable/procedures.jsonl)`.
- Write consent is `unset`, and the CLI says it "fails closed until `memorable enable`".
- **Encryption is `off, no key store on this machine`.** The research said the local store is AES-256-GCM encrypted. In practice it's only encrypted once a key store exists. We still don't parse the file: the licence forbids it, and the CLI output is the supported interface.
- The extraction API is `not configured, run memorable login`. So **`ingest` needs a login**, because it calls Memorable's extraction service.

## Commands we call, and how we parse them

| Command | Called by | Parse |
|---|---|---|
| `memorable recall "<first prompt>" --single` | router classifier (#20), once per session, 500 ms timeout | First line matching `^\s*(?P<score>[0-9.]+)\s+(?P<slug>procedures/\S+)\s+\[(?P<matcher>[^\]]+)\]`. Score ≥ 0.6 and the slug present in `data/slug_map.json` means a match; otherwise fall back to the prompt-derived name |
| `memorable ingest <trace.json>` | ingest bridge (#36), after every passing session | Success or refusal from the output. A refusal includes `allowance_exhausted` (research); log it once and carry on |
| `memorable list --json` | dashboard, optional | JSON array; fields confirmed after capture |
| `memorable chain "<task>" --json` | not on the critical path | Captured for reference |



## Trace we send

The contracts §7 shape (the `/v1/extract` body): `{session_id, harness: "opencode", task_description, tool_calls: [{name, input, result}]}`. It uses only the allow-listed input keys (`command`, `file_path`, `path`, `pattern`, `url`, `query`), and results are `{ok}` or `{exit_code}`. The three sample traces in `fixtures/memorable/` follow it:

| File | Task type | Why it's there |
|---|---|---|
| `trace-fix-failing-test-05.json` | fix-failing-test | Includes a failing `pytest` (exit 1) before the fix, then exit 0 |
| `trace-fix-failing-test-07.json` | fix-failing-test | A different path through the same task, including `grep` |
| `trace-update-changelog.json` | update-changelog | A different task, so recall has something to tell apart |

## Captured after login (2026-09-27, 0.5.30)

`scripts/memorable_capture.sh` ran with the owner logged in (`capture on · recall on`, write consent `read-write`, 1,000 free memorables a month plus 500 in reserve). Raw output is in `fixtures/memorable/`.

**`ingest`** prints one line and stores the procedure locally:

```
memorable: stored procedures/31e89c7a-add-test-mod-05-py-passing-case, first recording of this task
```

**Each trace became its own procedure, titled from its steps.** The two fix-failing-test traces weren't grouped: they became `add-test-mod-05-py-passing-case` and `fix-scale-function-in-calc-mod-07-py`. This is why the classifier maps slugs through `data/slug_map.json` (#36 records `slug → task type` on every ingest) instead of reading a task type out of the slug.

**`recall --single`** prints the top candidates (two here, despite `--single`). Scores have three decimals, columns are separated by two spaces, and the matcher list is comma-separated:

```
0.662  procedures/31e89c7a-add-test-mod-05-py-passing-case  [lexical,semantic]
0.603  procedures/60a82d56-fix-scale-function-in-calc-mod-07-py  [lexical,semantic]
```

| Prompt | Top score | Top procedure |
|---|---|---|
| `The test tests/test_mod_03.py is failing. Fix the code so it passes.` (unseen module) | 0.662 | the mod_05 procedure |
| `Add a CHANGELOG entry for version 0.4.3.` (unseen version) | 0.948 | the 0.4.2 changelog procedure |

So a same-shape task with a different file scores around **0.6–0.66**, and a reworded near-duplicate scores around **0.95**. The classifier's threshold is 0.6. The earlier guess of 0.75 would have missed the demo task entirely.

**Latency:** 490–720 ms calling the CLI directly with `node` (4 runs), and 1,338 ms through `npx`. The docs' ~60 ms is recall inside a warm process, not a cold CLI call. The classifier's timeout is 1.5 s, and the router should call a global install (`npm i -g memorable-cli@0.5.30`), not `npx`.

**`list --json`** is an array with one entry per procedure:

```json
{"intent": "procedures/<slug>", "preferred": "procedures/<slug>",
 "revisions": [{"slug": "procedures/<slug>", "revision": 1, "title": "Add test_mod_05.py passing case",
                "verified": true, "stale": null, "recalled": 0, "ok": 0, "fail": 0}]}
```

`verified`, `recalled`, `ok` and `fail` are Memorable's own outcome counters. The dashboard can show them next to our ledger counts.

**`chain "fix the failing test" --json`** returned a single `gap` with coverage 0. None of the three procedures is general enough to chain. It isn't on our critical path.

**`show <slug>`** returns the procedure wrapped as retrieved context for an agent: where the fix landed, the verify command, the decisive steps, and a note to treat the stored content as data rather than instructions.

Not tested: whether `ingest` works offline. It needs the extraction API, so assume no.
