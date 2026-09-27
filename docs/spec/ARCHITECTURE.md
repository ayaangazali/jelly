GRADUATE: architecture as built
===============================

The components and data flow as they exist on `main` at `e723076`, with file paths and line numbers; the trust boundaries; every failure mode and whether it fails open; and the design tradeoffs with the alternative that was rejected. Requirement ids (R1–R20) are defined in [PRODUCT.md](PRODUCT.md).

## Which doc is canonical for what

| Topic | Canonical | Notes |
|---|---|---|
| Shapes: ledger row, session log, metrics, registry, dataset records, Memorable trace, trace event, cost | [`graduate/contracts.md`](../../graduate/contracts.md) | "If code and this file disagree, this file is right." The disagreements found are listed [below](#where-the-docs-disagree-with-the-code) |
| Architecture after the research (what replaced the pack's design) | [`docs/PROJECT-BRIEF.md`](../PROJECT-BRIEF.md) § Architecture after the research | Overrides `02-project/architecture.md`, which is the pre-research pack |
| Decided stack | [`AGENTS.md`](../../AGENTS.md) § Decided stack | |
| Harness wire formats (who speaks what) | [`docs/research/harness-protocols.md`](../research/harness-protocols.md) | |
| Caching economics | [`02-project/cost-model.md`](../../02-project/cost-model.md) | |
| Local vs River training, the pretrained checkpoints | [`docs/pretrained-model.md`](../pretrained-model.md), [`docs/river-api.md`](../river-api.md) | |
| As-built components, data flow, failure modes, tradeoffs | **this file** | |

## Components

| Component | Code | Does |
|---|---|---|
| Router core | `graduate/router/app.py` | `POST /v1/chat/completions` (`:113-207`), `/healthz`, `/v1/models`. Reads the bearer as the session id (`:130-131`), asks each registered route whether to serve (`:132-137`), else forwards to the frontier with `model` replaced (`:140`) and `stream_options.include_usage` forced on streams (`:141-145`). Imports every module in `graduate/router/` at startup; one that fails to import is logged and skipped (`:210-214`) |
| Frontier client | `graduate/router/upstream.py` | Any OpenAI-compatible endpoint: `OPENAI_BASE_URL` (`:21`), key from env or `.env` in the cwd (`:15-19`), model from `OPENAI_MODEL` or `prices.json` (`:28-31`). No key → a local 401 `missing_api_key` (`:48-50`). Rewrites `max_tokens` to `max_completion_tokens` (`:56-58`) |
| Routing | `graduate/router/route.py` | `POST /api/sessions` registers the runner's prompt, repo, verify, force flag and task-type hint (`:67-73`). `classify_and_route` skips `sess-anon` (`:83-84`), classifies, reads `registry.json` (re-read on mtime change, `:18-26`) and returns the owned response only when the state is GRADUATED and a model is set (`:43`) |
| Classifier | `graduate/router/classify.py` | Once per session (`:47-48`): the runner's hint (`:49-50`), else `memorable recall --single` with score ≥ `GRADUATE_RECALL_MIN` 0.6 and a slug in `data/slug_map.json` (`:53-57`), else a slug of the normalized prompt, paths → `<path>`, digits → `<n>` (`:17-29`). Recall timeout 1.5 s (`:13`) |
| Owned serving | `graduate/router/river.py` | Generates the whole answer, then sends it as JSON or a synthesized SSE stream (`:46-123`). Any exception → returns `None`, so the frontier serves that call (`:60-75`) |
| Session log | `graduate/router/sessionlog.py` | After the last byte, one line per call to `sessions/<id>.jsonl`; streams reassembled (`:22-57`, `:60-84`). `GET /api/sessions/<id>/log` (`:90-95`) |
| Metrics | `graduate/router/metrics.py` | One `metrics.jsonl` line per call, cost per contracts §9 (`:33-42`), priced by the upstream's role (`:73`). Per-session sums in memory, rebuilt from the file at import (`:56-59,104`). `GET /api/sessions/<id>` (`:106`) |
| State and dashboard API | `graduate/router/state.py` | `GET /state` (`:78-96`), `GET /` serves `ui/index.html` (`:99-103`), `/bench/latest/results.json` (`:106-111`), `/ui` static (`:115`). `totals.saved_usd` sums `baseline.cost_usd − cost_usd` over owned exit-0 rows (`:46-56`) |
| Consent | `graduate/router/consent.py` | `GET/POST/DELETE /api/consent/<t>` (`:50-108`); names the backend Approve would use (`:18-25`) |
| Anthropic front door | `graduate/router/anthropic.py` | `POST /v1/messages`: translates to Chat Completions (`:22-60`), calls the same `chat_completions` handler (`:158-162`), translates back, streaming included (`:95-143`) |
| Sample flag | `graduate/router/sample.py` | `GET /api/sample` is true under `graduate up --demo` (`:9-11`) |
| Runner | `graduate/runner/__init__.py` | `graduate run`: registers the session (`:64-75`), launches `opencode run` with `GRADUATE_SESSION` and without `OPENAI_API_KEY` (`:88-99`), kills the process group at the timeout (`:102-107`), always runs the verify command in the repo (`:115`), writes one ledger row (`:132-160`), ingests passing frontier sessions into Memorable (`:157-158`), escalates failed owned sessions (`:175-179`) |
| Ledger | `graduate/ledger.py` | Append under `flock` (`:10-14`) |
| Watcher | `graduate/watcher/__init__.py` | Recomputes every task type from the whole ledger on each mtime change (`:33-104`, `:114-120`) |
| Registry | `graduate/registry.py` | The state machine (`:40-59`, `:127-164`); locked read-modify-write with atomic replace (`:100-116`); event log capped at 200 (`:183-189`) |
| Dataset | `graduate/registrar/dataset.py` | `data/<t>.chat.jsonl`, `.tok.jsonl`, `.neg.jsonl` from the ledger and session logs (`:80-133`) |
| Trainer | `graduate/registrar/train.py` | `LocalBackend` (LoRA on `GRADUATE_LOCAL_MODEL`, default Qwen2.5-Coder-0.5B, CPU, `:31`, `:125-280`) or `RiverBackend` (`:283-322`), chosen by `backend()` (`:325-334`). `parse()` turns Qwen text into OpenAI tool calls (`:97-122`) |
| Escalator | `graduate/escalator/__init__.py` | Snapshot (`:32-37`), forced failure (`:40-49`), reset + negative + probation + frontier rerun (`:65-147`) |
| Memorable bridge | `graduate/memorable/bridge.py` | Writes the allow-listed trace and runs `memorable ingest` (`:37-103`) |
| GBrain hook | `graduate/gbrain.py` | On GRADUATED or PROBATION: writes `GRADUATED.md` and runs `gbrain put graduated --force` (`:23-40`) |
| MCP server | `graduate/mcp.py` | stdio JSON-RPC, read-only tools `graduate.status` and `graduate.savings` (`:8-80`) |
| Trace | `graduate/trace.py` | `trace.jsonl` and `terminal.log` for Under the hood (`:11-34`) |
| CLI | `graduate/cli.py` | `graduate run / init / up / bench / results / train` (`:26-41`). `up` serves on 127.0.0.1:4141 only (`:198`, `:236`) and starts the watcher unless `--demo` (`:213-216`) |
| Dashboard | `ui/index.html`, `ui/present.js` | Views `#/`, `#/show`, `#/compare`, `#/system`, `#/setup`, `#/task/<t>`, `#/consent/<t>`, `?present` (`ui/index.html:275-281,409`) |

## Data flow, one session

1. `graduate run --task-file demo-repo/tasks/NN.json --repo demo-repo` makes `sess-<12 hex>` (`runner:56`), snapshots the repo (`runner:63`, `escalator:32-37`) and registers the session with the router (`runner:64-75`).
2. OpenCode starts with `apiKey = {env:GRADUATE_SESSION}` (`demo-repo/opencode.json`), so every call carries the session id as its bearer.
3. Each call: the router classifies once per session (`classify.py:46-64`), reads the registry, and either serves from the owned model (`river.py`) or forwards to the frontier (`app.py:139-207`).
4. After the last byte, the on-call hooks write `sessions/<id>.jsonl` and `metrics.jsonl` (`app.py:60-76`, `:79-94`). A 4xx/5xx from the frontier runs no hooks (`app.py:180-190`).
5. The agent exits (or is killed at the timeout). The runner runs `verify` with `shell=True` in the repo (`runner:115`); a timeout records exit 124 (`runner:117`).
6. The runner fetches the session aggregate and log (`runner:46-52`) and appends one ledger row. `routed_to` and `model` are the last call's (`runner:51,131`); `task_type` is the metrics aggregate's (`runner:134`).
7. A passing frontier session is ingested into Memorable (`runner:157-158`). A failed owned session is escalated (`runner:175-179`).
8. The watcher sees the ledger change within a second and recomputes counts; at N it flips READY (`watcher:85-95`).
9. `python -m graduate.registrar.dataset <t>` builds the records; the consent screen shows them; Approve launches the trainer (`consent.py:78-96`).
10. The trainer graduates the task type (`train.py:435-445`); the next session's calls route to the owned model.

## Files on disk

All in the directory the router, runner and watcher are started from. They must share one directory: the runner writes `ledger.jsonl` relative to its cwd (`graduate/ledger.py:7`), the router writes `sessions/` and `metrics.jsonl` relative to its own (`sessionlog.py:18`, `metrics.py:20`), and the dataset builder reads both from its cwd (`dataset.py:15-16`). Shapes: [contracts.md](../../graduate/contracts.md).

`registry.json`, `registry.lock`, `ledger.jsonl`, `metrics.jsonl`, `sessions/<id>.jsonl`, `sessions/<id>.diff`, `data/<t>.{chat,tok,neg,loss}.jsonl`, `data/<t>.train.log`, `data/checkpoints/<t>-v<n>/`, `data/slug_map.json`, `data/traces/<id>.json`, `trace.jsonl`, `terminal.log`, `GRADUATED.md`, `prices.json`, `.env`.

## Trust boundaries

| Boundary | What crosses | What is enforced | Gap |
|---|---|---|---|
| Agent → router | The session id as bearer; the full request | The upstream key is never given to the agent (`runner:89`); the bearer never goes upstream (`app.py:140` builds a new body, `upstream.py:51-54` sets its own header) | Any process that can reach the port can use the router's key. `graduate up` binds 127.0.0.1 (`cli.py:236`); `GRADUATE_HOST=0.0.0.0` (Docker) removes that |
| Bearer → filesystem | The session id becomes a file name | `sess-[\w-]+` only, else `sess-anon` (`sessionlog.py:19,61-62`) | None known |
| URL path → filesystem | `/api/consent/<t>`, `/api/sessions/<id>/log` | Consent looks the name up in the registry first (404 otherwise, `consent.py:52-54`); log path checked by the same regex (`sessionlog.py:93`); dataset names must match `[A-Za-z0-9][A-Za-z0-9_-]*` (`dataset.py:81-82`) | None known |
| Agent → verifier | The repo the agent just edited | Verify runs in the repo only (`runner:115`) | **The agent can edit what verifies it** (#110): test files, `conftest.py`, `pytest.ini`, a skip marker. Nothing checks the diff. A gamed pass counts toward N and becomes a training record |
| Local data → River | Training records | Consent per task type; the screen names the destination (`consent.py:18-25`) | With `RIVER_API_KEY` set and `GRADUATE_OWNED_BACKEND` unset, Approve trains on River (`train.py:333`); `graduate up` warns (`cli.py:229-234`) |
| Session → Memorable | A trace of the session | Only `command, file_path, path, pattern, url, query` argument keys, prompt cut to 200 chars, no file contents or outputs (`bridge.py:10,37-58`) | None known |
| Owned model → agent | Tool calls from a 0.5B model | Every owned session is verified (`runner:115`); failure resets the repo (`escalator:75-80`) | Tool calls execute in the agent before verify runs; the reset is scoped to the repo pathspec `.` (`escalator:79-80`), so writes outside the repo are not undone |

## Failure modes and the fail-open rule

The rule ([AGENTS.md](../../AGENTS.md#hard-rules-from-the-build-plan)): every error path ends at "the frontier model handles it". Where it holds and where it does not:

| Failure | Behaviour | Fails open? | Where |
|---|---|---|---|
| Owned model raises (missing key, missing checkpoint, OOM in generate) | That call is served by the frontier; an `error` event is written | Yes, per call | `river.py:60-75` |
| `GRADUATE_OWNED_BACKEND=none` | Every owned call raises, so the frontier serves everything | Yes | `train.py:329-330` |
| Router plug-in module fails to import | Logged and skipped; the core proxy still serves | Yes | `app.py:210-214` |
| An on-call hook raises | Logged and skipped | Yes | `app.py:72-76` |
| Frontier unreachable | 502 `upstream_error` | Nothing to fall back to | `app.py:153-165` |
| Frontier 4xx/5xx (429, 401, 500) | Status and body passed through unchanged; nothing logged | Nothing to fall back to | `app.py:180-190` |
| Memorable missing or slow | Classifier falls back to the prompt slug after ≤1.5 s; ingest skipped with one warning | Yes | `classify.py:32-43`, `bridge.py:80-86` |
| GBrain missing | Graduation completes; the trace says `skipped` | Yes | `gbrain.py:36-37` |
| Router down during a run | The runner still verifies and writes a row (task type `unknown`, frontier) | Yes | `runner:37-43` |
| Escalation itself raises | The failed row is already on the ledger; the runner returns it | Yes | `runner:176-179` |
| Escalation rerun hits a dead frontier (429/401) | The rerun runs a whole agent session anyway and ends at exit 1 | Degrades: costs a full session for nothing (#111) | `escalator:125-132` |
| Every call in a session fails upstream | No metrics, so the row's `task_type` is `unknown` and `model` `unknown`: a real failure vanishes from its task type (#111) | Silent | `runner:130-134`, `app.py:185-187` |
| Trainer raises or gets SIGTERM | Back to READY with an `error` event | Yes | `train.py:387-389,453-463` |
| Trainer SIGKILLed or OOM-killed | Stays TRAINING until another training run starts | No (#116, PR #123) | `train.py:341-360,378` |
| Trainer can't be spawned after Approve | Task type left in TRAINING, request 500s | No | `consent.py:91-94` |
| Malformed line in the middle of `ledger.jsonl` | `/state` skips it (`state.py:36-43`); the watcher raises and its thread dies | No, silently | `watcher:26`, `watcher:114-120` |
| Session log missing for a ledger row | Record skipped and counted in `skipped` | Yes | `dataset.py:101-104` |
| Session longer than the context cap | Truncated and counted in `truncated` | Yes, visibly | `dataset.py:76-77` |

## Tradeoffs

| Decision | Rejected alternative | Why | Canonical |
|---|---|---|---|
| **A proxy** (base-URL swap) | A harness plugin, an SDK wrapper, or an agent skill | A proxy sees every call from any harness with one setting and needs no change in the agent; a plugin or skill is per-harness and sees only what the harness hands it; an SDK wrapper needs code changes in every caller. The cost: one more hop, and the proxy must be exactly transparent (R1) | [`02-project/architecture.md`](../../02-project/architecture.md) Design principle 2 |
| **OpenAI Chat Completions** as the core wire format, Anthropic `/v1/messages` translated onto it | Anthropic Messages as the core | OpenCode (the demo harness) and River's serving speak Chat Completions; one core path means one set of hooks, logs and tests. `/v1/messages` is a translation front door onto the same handler (`anthropic.py:158-162`), not a second upstream: Claude Code's calls go to the OpenAI-compatible frontier | [`docs/PROJECT-BRIEF.md`](../PROJECT-BRIEF.md) § What the research changed, row 1; [`harness-protocols.md`](../research/harness-protocols.md) |
| **Local LoRA training** as the working backend, River behind the same interface | River only | The River account has no credits (`insufficient_funds`). `train(chats, name, log)` / `complete(model, messages, tools)` is one interface with two backends (`train.py:125,283`); the checkpoint path picks the backend at serve time (`train.py:331-332`) | [SUBMISSION.md](../../SUBMISSION.md) § Sponsors; [`docs/pretrained-model.md`](../pretrained-model.md) |
| **The verify command's exit code as the only label** | A reward model, an LLM judge, human labels | Free, unambiguous, already produced by the work. Known holes: the agent can edit the tests, add a skip marker, patch the code under test from a `conftest.py`, or set `addopts = --collect-only` (both checked by hand: exit 0); pytest's summary parse ignores skips (`reward.py:17`); `files_touched_outside_scope` is never computed. All tracked in #110 | [`02-project/graduate-spec.md`](../../02-project/graduate-spec.md) §2; #110 |
| **N = 5** verified runs, `GRADUATE_N` | A learned threshold or a confidence estimate | Simple and visible on screen. How many runs a task type needs is an open question; every owned session is verified, so a low N costs latency and escalations, not correctness | [AGENTS.md](../../AGENTS.md) Decided stack; [SUBMISSION.md](../../SUBMISSION.md#honest-limits) |
| **Caching-on frontier baseline** | Uncached list price | Caching discounts re-sent input by 90% on both providers; a baseline without it inflates savings. Cached tokens are billed at the cached rate (`metrics.py:33-42`) | [`02-project/cost-model.md`](../../02-project/cost-model.md); contracts §9 |
| **Any OpenAI-compatible upstream** (OpenRouter, a stub) via `OPENAI_BASE_URL` | A provider SDK | `upstream.py:21-22` posts to `$OPENAI_BASE_URL/chat/completions` with a bearer key and nothing provider-specific, so OpenRouter or `scripts/stub-upstream.py` drop in. Untested against OpenRouter: its `usage` must carry `prompt_tokens_details.cached_tokens` for the cached-rate math, and `prices.json`'s `frontier` block must hold that model's prices, because cost is priced by role, never by the model id the upstream reports (`metrics.py:35`) | `graduate/router/upstream.py` |
| **Whole-answer owned generation, synthesized stream** | Token streaming from the owned model | Local generation is CPU-bound and short (≤384 new tokens, `train.py:274`); synthesizing the SSE keeps one code path for tool-call chunks (`river.py:23-43`) | `graduate/router/river.py` |
| **Greedy decoding** for the owned model | Sampling | Repeatable evals and a stable demo (`train.py:275`) | this file |

## Where the docs disagree with the code

Found while writing this spec. The code is what runs; each doc line should be corrected or the code changed.

| # | Doc says | Code does | Code |
|---|---|---|---|
| C1 | `02-project/graduate-spec.md` §3 and `02-project/architecture.md` §2: the Watcher reads Memorable procedures | The watcher reads `ledger.jsonl` only; Memorable is written to, never counted from | `watcher/__init__.py:19-26` |
| C2 | `02-project/architecture.md`: classification step 2 is embedding similarity; AGENTS.md and SUBMISSION.md: the fallback is a "normalized-prompt hash" | No embeddings. The fallback is a readable slug of the normalized prompt, not a hash; in the demo the task file's `task_type` decides | `classify.py:17-29,49-50` |
| C3 | `02-project/graduate-spec.md` §4: READY means "dataset built" | READY builds nothing; Approve returns 409 until `python -m graduate.registrar.dataset <t>` has run | `consent.py:85-87`, `scripts/demo.sh:115` |
| C4 | contracts §1: PROBATION → TRAINING "retrain includes the negatives"; `ui/index.html:519` on the PROBATION consent page: "plus N failing runs as examples of what not to do" | The trainer reads only `data/<t>.chat.jsonl` (contracts §6c itself says negatives aren't SFT-trained). The UI's N is `failed_runs`, which counts failed **frontier** sessions, not owned failures | `train.py:405-413`, `ui/index.html:513,519`, `watcher/__init__.py:65` |
| C5 | contracts §1: GRADUATED → PROBATION also when "the owner demotes it" from the dashboard | No demote endpoint or UI action exists; only the escalator demotes | `escalator/__init__.py:107-108` |
| C6 | contracts §1: TRAINING → READY when "stale for over an hour" | Checked only when a trainer starts, so a killed trainer can stay TRAINING indefinitely (#116) | `train.py:378` |
| C7 | contracts §4: the router "drops the extra usage-only chunk if the client didn't ask for it" | True on the owned path only. The frontier path relays every byte, usage chunk included; `test_stream_passthrough_in_order` asserts exactly that | `app.py:194-207`, `river.py:113-117` |
| C8 | contracts §4: a usage mapping row for "Anthropic Messages" as an upstream | There is no Anthropic upstream; `/v1/messages` is translated onto the OpenAI-compatible frontier, and usage is mapped the other way for the response | `anthropic.py:63-69,158-162` |
| C9 | `02-project/architecture.md` §4 and graduate-spec §3: the escalator verifies "after a graduated call" and on "low confidence" | Verification is per session in the runner; there is no confidence signal | `runner:115,175` |
| C10 | `docs/QA.md` step 15: Activity says "Training started on River" | With no River key the event says "on this machine" | `consent.py:25,95` |
| C11 | `ui/index.html:343` describes the rerun as sending "header x-graduate-force: frontier" | The flag is internal: the runner registers `force_frontier`, and `route.py` builds the header dict itself. A client can't send `x-graduate-force`; the `owned` value in `route.py:43` is unreachable | `route.py:42-43,86` |
| C12 | `SUBMISSION.md`: the router serves Claude Code via `/v1/messages` | It does, but Claude Code's real key isn't a `sess-` id, so its calls are `sess-anon`: never classified, never owned-routed, all logged to `sessions/sess-anon.jsonl` | `anthropic.py:153`, `app.py:131`, `route.py:83-84` |
| C13 | `scripts/compare.py` docstring: refuses stub data by the stub's model id | The stub's id `gpt-5.6-terra` is also the real default frontier in `fixtures/prices.example.json`, so a real Terra ledger would be refused | `scripts/compare.py:22`, `fixtures/prices.example.json` |
| C14 | contracts §2: `routed_to` is "which upstream served this session" | It is the upstream of the session's last call. A session where the owned model errored and the frontier served the rest can be recorded as `frontier`, pass, and count toward graduation and training | `runner:51,131`, `river.py:60-75` |
| C15 | contracts §10 and `graduate/reward.py:12`: `files_touched_outside_scope` feeds the reward | No ledger row carries it; the runner never computes it (#110) | `runner:132-156` |
