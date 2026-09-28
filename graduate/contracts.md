# Contracts

Every shape that crosses a component boundary lives here. If code and this file disagree, this file is right, and a change to a shape starts as a comment on #11.

Example files for each shape are in `fixtures/`, and `registry.example.json` is at the repo root. They all parse, and they agree with each other and with the sample data in `mock-up/index.html`.

All files are local, UTF-8 and append-only unless noted. Timestamps are ISO 8601 in UTC (`2026-09-27T21:14:03Z`). Money is USD as a float. Token counts are integers.

---

## 1. States and transitions

| State | Meaning |
|---|---|
| `LEARNING` | Fewer than N passing frontier sessions. Every session goes to the frontier model |
| `READY` | At least N passing frontier sessions. Waiting for the owner to approve the training data. Still routed to frontier |
| `TRAINING` | Approved; the River training loop is running. Still routed to frontier |
| `GRADUATED` | A trained checkpoint exists. Sessions go to the owned model and are verified after every session |
| `PROBATION` | The owned model failed verification `GRADUATE_FAIL_LIMIT` times, or the owner sent it back. Routed to frontier until retrained |

N is `GRADUATE_N` (default 5). The fail limit is `GRADUATE_FAIL_LIMIT` (default 3).

| From | To | Allowed when | Who does it |
|---|---|---|---|
| `LEARNING` | `READY` | `verified_runs >= N` | watcher (#19) |
| `READY` | `TRAINING` | `consent == true` | consent endpoint (#25) or the trainer CLI (#22) |
| `TRAINING` | `GRADUATED` | a checkpoint was saved | trainer (#22) |
| `TRAINING` | `READY` | training failed, or `TRAINING` is stale for over an hour | trainer (#22) |
| `GRADUATED` | `PROBATION` | `failures_since_graduation >= GRADUATE_FAIL_LIMIT`, or the owner demotes it | escalator (#23), dashboard |
| `PROBATION` | `TRAINING` | `consent == true` (retrain on the passing runs; negatives are kept but not trained on, §6c) | consent endpoint (#25) |

Anything else raises `IllegalTransition`. Consent is checked on the way **into** `TRAINING`, not on the way into `READY`: reaching the bar is automatic, sending data to River never is.

---

## 2. Run ledger — `ledger.jsonl`

One row per session, written by the runner (#34) after the verify command exits. Graduation is counted from here and nowhere else.

| Field | Type | Meaning |
|---|---|---|
| `session_id` | string | `sess-` plus 12 hex characters. Also the bearer token the agent sends to the router |
| `task_type` | string | Slug from the classifier (#20), e.g. `fix-failing-test`. `unknown` if unmatched |
| `procedure_slug` | string or null | Memorable procedure this session matched or created, e.g. `procedures/7c2e19ab-fix-failing-test` |
| `prompt` | string | The task prompt given to the agent |
| `repo` | string | Path of the repo the task ran in |
| `start_commit` | string | `git rev-parse HEAD` before the agent started |
| `verify_command` | string | Command the runner ran after the agent exited |
| `exit_code` | int | Exit code of `verify_command`. `124` means the agent timed out. A verify that exits 0 is recorded as `1` when the row is `tampered`, or when the command runs `pytest` and its summary does not show at least one test with all of them passed |
| `tests_passed` | int or null | Parsed from the pytest summary line |
| `tests_total` | int or null | Parsed from the pytest summary line |
| `routed_to` | `"frontier"` or `"owned"` | Which upstream served this session |
| `model` | string | Frontier model id, or the River checkpoint path / deployment model |
| `turns` | int | Model calls in this session (from the router's session aggregate) |
| `tool_calls` | int | Tool calls the model made across the session |
| `input_tokens` | int | Prompt tokens across the session, cached ones included |
| `cached_input_tokens` | int | The cached part of `input_tokens` |
| `output_tokens` | int | Completion tokens across the session |
| `cost_usd` | float | Section 9 formula, summed over the session's calls |
| `wall_secs` | float | Agent start to verify exit |
| `started_at` | string | Timestamp |
| `ended_at` | string | Timestamp |
| `escalated_from` | string or null | For an escalation rerun: the failed owned session it replaces |
| `forced_failure` | bool | True only when `GRADUATE_FORCE_FAIL=1` faked the failure for the demo |
| `tampered` | bool | The agent added, changed or deleted a file under a `tests/` directory or a `conftest.py`, compared with the working tree when the session started |

A task type's `verified_runs` is the count of rows with `routed_to == "frontier"`, `exit_code == 0`, `escalated_from == null`. Escalation reruns don't count toward graduation, because they would reward the model for failing.

Example: `fixtures/ledger.example.jsonl`.

---

## 3. Session log — `sessions/<session_id>.jsonl`

One line per model call, written by the router (#35) after the response finishes. This is the training data. Never commit it.

| Field | Type | Meaning |
|---|---|---|
| `ts` | string | When the call finished |
| `session_id` | string | Same as the ledger |
| `upstream` | `"frontier"` or `"owned"` | Where the router sent it |
| `model` | string | Model id or checkpoint path used |
| `request` | object | The full Chat Completions request body as received, minus nothing |
| `response` | object | The full assistant message. For streams, the chunks reassembled: `{role, content, tool_calls, finish_reason}` with `tool_calls` merged by index |
| `usage` | object | `{input_tokens, cached_input_tokens, output_tokens}` normalized from the upstream's usage block |
| `latency_ms` | int | Request received to last byte sent |

The upstream API key is never written. The bearer token (the session id) is fine.

Example: `fixtures/session.example.jsonl`.

---

## 4. Metrics record — `metrics.jsonl`

One line per model call, written by the router (#17). The session aggregate the runner reads (`GET /api/sessions/<id>`) is the sum of these.

| Field | Type | Meaning |
|---|---|---|
| `ts` | string | Timestamp |
| `session_id` | string | `sess-anon` if the bearer isn't a session id |
| `task_type` | string | As classified for this session |
| `upstream` | `"frontier"` or `"owned"` | |
| `model` | string | |
| `input_tokens` | int | |
| `cached_input_tokens` | int | |
| `output_tokens` | int | |
| `tool_calls` | int | Tool calls in this response |
| `cost_usd` | float | Section 9 |
| `latency_ms` | int | |
| `stream` | bool | Whether the client asked for a stream |

Usage mapping by upstream:

| Upstream | `input_tokens` | `cached_input_tokens` | `output_tokens` |
|---|---|---|---|
| OpenAI Chat Completions | `usage.prompt_tokens` | `usage.prompt_tokens_details.cached_tokens` | `usage.completion_tokens` |
| River (OpenAI-compatible) | `usage.prompt_tokens` | `usage.prompt_tokens_details.cached_tokens` if present, else 0 | `usage.completion_tokens` |
| Anthropic Messages (#26 only) | `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` | `cache_read_input_tokens` | `output_tokens` |

Streamed OpenAI responses only include usage when the request has `stream_options.include_usage: true`. The router sets it on every streaming request, and drops the extra usage-only chunk if the client didn't ask for it.

Example: `fixtures/metrics.example.jsonl`.

---

## 5. Registry — `registry.json`

One object per task type, plus an event list. Rewritten atomically by `graduate/registry.py` (#18); nothing else writes it.

```
{ "task_types": { "<task_type>": TaskType, ... }, "events": [Event, ...] }
```

**TaskType**

| Field | Type | Meaning |
|---|---|---|
| `title` | string | Human name for the dashboard, e.g. "Fix a failing test" |
| `state` | string | Section 1 |
| `consent` | bool | Owner approved sending this task type's data to River |
| `verify_command` | string | Default verify command for the task type |
| `procedure_slug` | string or null | Memorable procedure the classifier maps to this task type |
| `verified_runs` | int | Section 2 count |
| `failed_runs` | int | Frontier sessions with `exit_code != 0` |
| `baseline` | Numbers or null | Averages over verified frontier sessions |
| `current` | Numbers or null | Averages over verified owned sessions since graduation |
| `model` | string or null | River checkpoint path, e.g. `river://run-4c1e/sampler_weights/update-changelog-v1` |
| `serving` | `"deployment"`, `"checkpoint"` or null | How the router reaches the model (#37) |
| `deployment` | object or null | `{base_url, model}` when `serving == "deployment"` |
| `trained_on_runs` | int | Sessions in the last training run |
| `graduated_at` | string or null | Timestamp |
| `verified_since_graduation` | int | Owned sessions that passed |
| `failures_since_graduation` | int | Owned sessions that failed. Reset on retrain |

**Numbers**: `{turns, tool_calls, cost_usd, wall_secs}`, all floats.

**Event**: `{ts, kind, task_type, text}`. `kind` is one of `run`, `ready`, `consent`, `training`, `graduated`, `failed`, `escalated`, `probation`, `error`. `text` is one plain sentence for the dashboard log. The list is capped at the newest 200.

Example: `registry.example.json` has one task type in every state, and its four original task types match the mock-up.

---

## 6. Training data

### 6a. SFT chat record — `data/<task_type>.chat.jsonl`

One record per **passing session** (not per call). The last call of a session already carries the whole conversation in its request, so the record is that request's messages plus the final response. The consent screen shows these records verbatim.

| Field | Type | Meaning |
|---|---|---|
| `messages` | list | OpenAI chat messages: `system`, `user`, `assistant` (with `tool_calls`), `tool` (with `tool_call_id`) |
| `tools` | list | Tool specs from the request, flattened to River's `ToolSpec`: `{name, description, parameters}` |
| `metadata` | object | `{task_type, session_id, verify_command, exit_code, turns, tool_calls}` |

### 6b. River wire record — `data/<task_type>.tok.jsonl`

Built by River's own renderer, not by hand. The chat template, tool-call format and weight shifting all come from the SDK (`river-client` 0.12.0, verified by reading the installed package):

```python
from river_client.renderers import get_renderer, TrainOnWhat
renderer = get_renderer(BASE_MODEL)
example = renderer.build_training_example(record["messages"], tools=record["tools"], train_on=TrainOnWhat.ALL_ASSISTANT)
wire = example.to_dict()
```

| Field | Type | Meaning |
|---|---|---|
| `input_ids` | list of int | Tokens of the whole rendered session |
| `attention_mask` | list of int | All ones, same length |
| `weights` | list of float | Loss weight per position: non-zero only on assistant tokens, already left-shifted and normalized by `to_dict()` |

This is exactly what `model.train_step(data=[wire, ...], lr=..., loss_fn="cross_entropy")` takes. River's docs show `{input_ids, target_tokens, weights}`; the SDK's `to_dict()` produces the shape above, and the SDK is what the server accepts.

### 6c. Negative record — `data/<task_type>.neg.jsonl`

The 6a shape for a failed owned session, with `metadata.exit_code != 0` and `metadata.negative = true`. Not trained on by SFT, including on a retrain. Kept on disk for RL.

Examples: `fixtures/sft-chat.example.json`, `fixtures/sft-wire.example.json`.

---

## 7. Memorable trace

What `graduate/memorable` (#36) writes to `data/traces/<session_id>.json` and passes to `memorable ingest`. It's the `POST /v1/extract` shape.

| Field | Type | Meaning |
|---|---|---|
| `session_id` | string | |
| `harness` | `"opencode"` | Gets Memorable's curated OpenCode tool registry |
| `task_description` | string | The task prompt, at most 200 characters |
| `tool_calls` | list | `{name, input, result}` in call order |
| `tool_calls[].input` | object | Only the allow-listed keys: `command`, `file_path`, `path`, `pattern`, `url`, `query` |
| `tool_calls[].result` | object | `{ok: bool}` for ordinary tools, `{exit_code: int}` for commands |

The last entry is always the runner's verify command with its real `exit_code`. File contents and command output are never included.

Example: `fixtures/memorable-trace.example.json`.

---

## 8. Trace event — `trace.jsonl`

Written by `graduate.trace.emit(...)` (#12) whenever a component launches a process, calls a service or changes state. The live Under the hood view (#39) renders these. The router also keeps the newest 200 in memory for `/state`.

| Field | Type | Meaning |
|---|---|---|
| `ts` | string | Timestamp |
| `session_id` | string or null | |
| `who` | string | `"<from> → <to>"`, e.g. `"Router → OpenAI"` |
| `call` | string | The exact command or API call, e.g. `POST https://api.openai.com/v1/chat/completions` |
| `result` | string | One line: exit code, status, slug, checkpoint path, loss |
| `issue` | int | The issue that owns this call |
| `nodes` | list of string | Diagram nodes to light up |
| `edges` | list of string | Diagram edges to light up |

Node ids: `runner`, `memorable`, `openai`, `opencode`, `router`, `river`, `dashboard`, `pytest`, `disk`, `registry`, `consent`, `ledger`, `watcher`, `rivertrain`, `registrar`, `escalator`.

Edge ids: `launch`, `ingest`, `chat`, `recall`, `frontier`, `owned`, `log`, `reads`, `verify`, `exit`, `tail`, `ready`, `ask`, `approved`, `train`, `serve`, `graduate`, `state`, `failed`, `rerun`.

These are the ids in `mock-up/index.html` (`NODES`, `EDGES`). Adding one means adding it there too.

The runner's live agent output goes through `graduate.trace.terminal(line)` to `terminal.log`, one line per output line, not to `trace.jsonl`. ANSI CSI and OSC sequences are stripped on write.

Example: `fixtures/trace.example.jsonl`.

### `/state` `config`

| Field | Type | Meaning |
|---|---|---|
| `n` | int | Verified runs to graduate (`GRADUATE_N`) |
| `fail_limit` | int | Failures before probation (`GRADUATE_FAIL_LIMIT`) |
| `backend` | string | `river`, `local` or `none`: where a new training run goes, as the consent screen reports it (#96). The dashboard labels the serving node from the graduated checkpoint (`river://` or a local path) instead |

Example: `fixtures/state.example.json`.

---

## 9. Cost

Per call:

```
cost_usd = ((input_tokens - cached_input_tokens) * input_price
            + cached_input_tokens * cached_input_price
            + output_tokens * output_price) / 1_000_000
```

Prices are per million tokens and live in `fixtures/prices.example.json`, keyed by role (`frontier`, `owned`) so the model id can change without touching code. Copy it to `prices.json` and put the real model ids and prices in before the demo.

| Role | Model | Input | Cached input | Output | Training | Source |
|---|---|---|---|---|---|---|
| `frontier` | GPT-5.6 Terra | 2.00 | 0.20 | 12.00 | — | Pack's pricing table, checked 2026-09-26; cached input is 10% of input |
| `owned` | Qwen3.6-35B-A3B on River | 0.33 | 0.066 | 0.82 | 1.00 | river.ai preview rates; cached prompt tokens are 20% of the prompt rate |

Re-check both on the providers' pricing pages the morning of the demo. The baseline is always the frontier with caching on; a comparison against uncached frontier prices is not allowed on screen.

Training cost for a run is `training_price * total_tokens_trained / 1e6`, where `total_tokens_trained` is the sum of `len(input_ids)` over the batches actually sent, times steps.

---

## 10. RL episode — `data/rl.jsonl` (#30 only)

| Field | Type | Meaning |
|---|---|---|
| `prompt` | string | |
| `trajectory` | list | `{tool, args}` in order |
| `verify_command` | string | |
| `exit_code` | int | |
| `tests_passed` | int | |
| `tests_total` | int | |
| `tool_calls` | int | |
| `files_touched_outside_scope` | int | Files changed outside the task's module and test file |
| `reward` | float | `graduate.reward.reward(episode)` (#14) |

Example: `fixtures/rl-episode.example.json`.
