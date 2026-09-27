GRADUATE: acceptance test plan
==============================

Every requirement in [PRODUCT.md](PRODUCT.md) (R1–R20) and every failure mode in [ARCHITECTURE.md](ARCHITECTURE.md) mapped to a test that can fail. Each test says what it proves, its level, how to run it, what you must observe, the edge cases, and whether it exists today. "Exists" means the named test is on `main` at `e723076`; "TODO" means it has to be written, and "fails on main" means the expected result below is not what the code does today (the test is the acceptance bar for the fix).

When organizer requirements land, start at [Requirements intake](#requirements-intake).

## Levels

| Level | Meaning | Costs |
|---|---|---|
| unit | One function, in-process, no network | $0, seconds |
| integration | The router app in-process (`router` + `stub` fixtures in `tests/conftest.py`), or a module's `python -m` self-check | $0, seconds |
| e2e offline | Real processes: router, watcher, real OpenCode, real pytest in `demo-repo/`, frontier = `scripts/stub-upstream.py` | $0, minutes |
| e2e live | As e2e offline, frontier = real OpenAI | Money and the account's daily request cap (#114) |
| visual | A headless browser on the dashboard: screenshots, console, layout | $0 |
| independent re-check | A person or agent who didn't write the code recomputes a claim from raw files | $0 unless it re-runs live |

## Environments

**ENV-U (unit, integration).** Python 3.12 venv with `pip install -e '.[test,train]'`. In the checkout under test:

```sh
export PYTHONPATH=$PWD
python -c 'import graduate;print(graduate.__file__)'
```

The second line must print a path inside this checkout; an editable install elsewhere otherwise tests the wrong tree. Then `make check && make test`, or `pytest -q <test id>`.

**ENV-O (e2e offline).** From the repo root, with earlier state moved aside (`ledger.jsonl registry.json metrics.jsonl trace.jsonl terminal.log sessions/ data/` into `backups/`) and `scripts/reset-demo.sh clean`. Never port 4141 (another lane's router may hold it). Three terminals, all in the repo root:

```sh
python3 scripts/stub-upstream.py 4211 /tmp/graduate-auth.log
OPENAI_BASE_URL=http://127.0.0.1:4211/v1 OPENAI_API_KEY=sk-stub uvicorn graduate.router.app:app --port 4210
python -m graduate.watcher
```

and for every `graduate run`:

```sh
export GRADUATE_ROUTER=http://localhost:4210
export OPENCODE_CONFIG_CONTENT='{"provider":{"graduate":{"options":{"baseURL":"http://localhost:4210/v1"}}}}'
```

**ENV-L (e2e live).** ENV-O without the stub: the router gets a real `OPENAI_API_KEY` in its own environment only, and `prices.json` names a model the account can call. Before any run: LV-04 (request headroom), and a budget guard that sums `cost_usd` over `ledger.jsonl` and stops at the agreed cap. The account is on the free tier (50 requests/day/model, #114), so every ENV-L test is blocked until #114 or the owner assigns the budget.

**ENV-H (heavy model work).** Torch training or owned inference. One job per machine at a time (take the machine's GPU lock); a second model in memory is how attempt 1 of the live training got OOM-killed (test report §4).

## Summary

| Area | Tests | Exist | TODO | TODO that fail on main |
|---|---|---|---|---|
| Proxy passthrough and streaming (PX) | 11 | 8 | 3 | 1 |
| Session identity (SI) | 6 | 3 | 3 | 0 |
| Classification (CL) | 5 | 2 | 3 | 0 |
| Verification and gaming (VF) | 7 | 1 | 6 | 4 |
| Ledger, watcher, N (LW) | 8 | 3 | 5 | 3 |
| Consent honesty (CO) | 5 | 2 | 3 | 2 |
| Dataset correctness, stub isolation (DS) | 8 | 5 | 3 | 1 |
| Training (TR) | 8 | 5 | 3 | 1 |
| Routing to owned (RO) | 6 | 4 | 2 | 0 |
| Parsing owned tool calls (PA) | 3 | 2 | 1 | 0 |
| Escalation (ES) | 4 | 1 | 3 | 2 |
| Probation (PB) | 3 | 1 | 2 | 0 |
| Dashboard (UI) | 10 | 6 | 4 | 0 |
| MCP (MC) | 3 | 2 | 1 | 0 |
| `/v1/messages` (AM) | 4 | 1 | 3 | 0 |
| GBrain (GB) | 3 | 2 | 1 | 0 |
| Memorable (ME) | 4 | 1 | 3 | 0 |
| Cost math (CM) | 5 | 3 | 2 | 0 |
| Live account limits (LV) | 5 | 3 | 2 | 0 |
| macOS portability (MAC) | 3 | 1 | 2 | 1 |
| Full loop e2e (E2) | 2 | 2 | 0 | 0 |
| Held-out eval protocol (EV) | 6 | 0 | 6 | 0 |
| **Total** | **119** | **58** | **61** | **15** |

"Exist" counts tests on `main` that assert the expected result automatically. Manual evidence from the 2026-09-27 test report is noted per test but counted as TODO until it is a repeatable command with an asserted result.

---

## PX: proxy passthrough and streaming (R1, R12)

**PX-01 · JSON passthrough is byte for byte.** R1 · integration · exists: `tests/test_router.py::test_json_passthrough_byte_for_byte`
Run: `pytest -q tests/test_router.py -k json_passthrough`
Expect: status 200; response bytes equal the stub's indented body (a re-serializing router fails); `content-type: application/json`.
Edge: unknown request fields reach the frontier (`x_unknown`, router self-check `graduate/router/app.py:254-262`); `model` is replaced by the frontier model (`app.py:140`).

**PX-02 · Streams pass through in order.** R1 · integration · exists: `tests/test_router.py::test_stream_passthrough_in_order` (with and without parallel tool-call deltas)
Run: `pytest -q tests/test_router.py -k stream_passthrough`
Expect: response bytes equal the concatenated stub SSE; `content-type` starts `text/event-stream`; the frontier received `stream_options: {"include_usage": true}`.
Edge: interleaved argument deltas for two tool calls.

**PX-03 · A client that didn't ask for usage gets no usage-only chunk.** R1 · integration · TODO, **fails on main** (contradiction C7)
Setup: `router`+`stub` fixtures, `stream: true`, no `stream_options`.
Expect (contracts §4): no SSE event with `"choices": []` reaches the client; the session log still records usage. Today the frontier path relays it (`app.py:194-207`). Decide first: fix the code, or change contracts §4 and assert the opposite.

**PX-04 · Upstream errors come back unchanged and write nothing.** R1, R3 · integration · exists: `tests/test_router.py::test_upstream_errors_unchanged_and_unlogged` (400, 429, 500, 503 × stream/non-stream)
Expect: same status and body bytes; no `metrics.jsonl`, no `sessions/`.

**PX-05 · Unreachable frontier is a 502.** R1 · integration · exists: `tests/test_router.py::test_unreachable_frontier_is_502`
Expect: 502, `error.type == "upstream_error"`.

**PX-06 · A body that isn't a JSON object is a 400 and is never forwarded.** R1 · integration · exists: `tests/test_router.py::test_non_object_body_is_400_and_never_forwarded`
Expect: 400 `invalid_request_error` for `{not json`, `[]`, `"hi"` and an empty body; the stub saw no request; the working directory is still empty.

**PX-07 · `max_tokens` is sent as `max_completion_tokens`.** R1 · integration · exists: `tests/test_router.py::test_max_tokens_sent_as_max_completion_tokens`, `::test_max_completion_tokens_kept`
Expect: the frontier body has `max_completion_tokens` and no `max_tokens`; a client's own `max_completion_tokens` wins.

**PX-08 · No key: the error says how to fix it.** R1 · integration · exists: `tests/test_router.py::test_no_key_says_how_to_fix_it`
Expect: 401 `missing_api_key` naming `graduate init`, and no request leaves the router.

**PX-09 · A pasted control character never puts the key into an error.** R2 · integration · exists: `tests/test_router.py::test_a_pasted_control_character_never_puts_the_key_in_an_error`

**PX-10 · Streaming is not buffered.** R1 · e2e offline · TODO (manual evidence: the verify agent's run, 07-findings)
Setup: real sockets, because the in-process `ASGITransport` returns only once the response is complete: a small upstream on :4213 that sends 4 SSE chunks, the first at once and then one every 0.5 s; the router under `uvicorn` on :4212 with `OPENAI_BASE_URL=http://127.0.0.1:4213/v1`; an `httpx` streaming client that timestamps each chunk on arrival.
Expect: the first chunk arrives < 0.4 s after the request; last − first ≥ 1.4 s. A buffering router delivers all four within a few ms of each other and fails.

**PX-11 · A broken router plug-in doesn't take the proxy down.** R12 · integration · TODO
Setup: in a subprocess, append a temp directory holding `boom.py` (`raise RuntimeError`) to `graduate.router.__path__`, then import `graduate.router.app` (it imports every module on that path, `app.py:210-214`). Nothing is written into the source tree.
Expect: the import succeeds, the log line names `boom`, and `POST /v1/chat/completions` still answers 200 from the stub.

## SI: session identity (R2)

**SI-01 · The bearer never goes upstream; the key never reaches disk.** R2 · integration · exists: `tests/test_router.py::test_bearer_never_forwarded`
Expect: the frontier saw `Bearer <server key>`; the session id appears nowhere in the forwarded body or headers; every file in the workdir contains the session id and none contains the server key.

**SI-02 · The agent never holds the OpenAI key.** R2 · integration · exists: `tests/test_runner.py::test_the_agent_never_holds_the_openai_key`

**SI-03 · A non-`sess-` bearer is `sess-anon` and never owned-routed.** R2, R10 · integration · TODO
Setup: registry with the task type GRADUATED on a fake backend; call with `Authorization: Bearer sk-anything`.
Expect: the stub (frontier) received the call; the fake backend did not; the line is in `sessions/sess-anon.jsonl` (`app.py:131`, `route.py:83-84`).

**SI-04 · A path-shaped bearer can't escape `sessions/`.** R2 · integration · TODO
Setup: bearer `sess-../../x`, then `GET /api/sessions/sess-..%2F..%2Fx/log`.
Expect: the line lands in `sessions/sess-anon.jsonl`; no file outside `sessions/` is created; the GET is 404 (`sessionlog.py:19,61-62,93`).

**SI-05 · `/api/sessions` refuses a non-`sess-` id.** R2 · integration · TODO (manual evidence: 02-smoke; `test_title_call_first_still_classified_by_registered_session` covers only the accept path)
Expect: `POST /api/sessions {"session_id":"x"}` returns `{"ok": false, …}` and nothing is stored for `x` (`route.py:69-71`).

**SI-06 · Session aggregates survive a router restart.** R3 · integration · exists: `graduate.router.metrics` self-check (`tests/test_selfchecks.py`), which clears the in-memory sums and rebuilds them from `metrics.jsonl` (`metrics.py:56-59`)
Expect: `GET /api/sessions/<id>` returns the same turns, tokens and cost before and after `_load()`.

## CL: classification (R4)

**CL-01 · The runner's task type and prompt win over OpenCode's title call.** R4 · integration · exists: `tests/test_router.py::test_title_call_first_still_classified_by_registered_session`
Expect: with a hint, the session's task type is the hint; without one, it is named from the registered prompt (`the-test…`), not the title request.

**CL-02 · The prompt-slug fallback groups one task family.** R4 · unit · TODO
Run: `classify.name_from_prompt` on the prompts of `demo-repo/tasks/01.json` and `09.json`.
Expect: both return the same slug, and it contains neither a path nor a digit (`classify.py:17-29`). A prompt about a different task returns a different slug.

**CL-03 · Memorable recall maps through `slug_map.json`, with the score floor.** R4, R17 · unit · TODO
Setup: `MEMORABLE_BIN` = a script that prints `fixtures/memorable/recall-fix-failing-test.txt`; `data/slug_map.json` maps its slug to `fix-failing-test`.
Expect: task type `fix-failing-test`, and the trace's `result` contains the score and slug. With `GRADUATE_RECALL_MIN=0.99`: the prompt slug instead. With the slug missing from the map: the prompt slug.

**CL-04 · A slow or missing Memorable never stalls a call.** R4, R17 · integration · TODO
Setup: `MEMORABLE_BIN` = a script that sleeps 5 s; then `MEMORABLE_BIN=/nonexistent`.
Expect: each first call returns 200 within 2.0 s (the recall timeout is 1.5 s, `classify.py:13`); the task type is the prompt slug; the trace names `TimeoutExpired` / `FileNotFoundError` (`classify.py:36-38`).

**CL-05 · Unclassified sessions never graduate and are counted.** R4, R6 · integration · exists: watcher self-check (`unknown` ignored, `graduate/watcher/__main__.py:29,42`) and state self-check (`unclassified_runs`, `graduate/router/state.py:147`)

## VF: verification and its gaming routes (R5)

The known routes are from #110. Each gaming test uses the real runner on a scratch copy of `demo-repo` with broken state 01 planted, and a fake agent script (the pattern in `tests/test_runner.py`) that makes exactly the edit named. **Not verified** means both: after `python -m graduate.watcher --once` the task type's `verified_runs` is unchanged, and after `python -m graduate.registrar.dataset <t>` the session id is absent from `data/<t>.chat.jsonl`.

**VF-01 · Every session is verified once, in the repo, even after a crash or timeout.** R5 · integration · exists: `tests/test_runner.py::test_run_verifies_and_appends_one_ledger_row` (fix, no fix, crash, hang)
Expect: exactly one ledger row in contract shape; `exit_code` is verify's, or 124 when the agent was killed at the timeout; `tests_passed/tests_total` parsed; Memorable ingest called only on exit 0.

**VF-02 · Editing the test to pass is not verified.** R5, R8 · integration · TODO, **fails on main** (#110)
Agent edit: `tests/test_mod_01.py` body → `assert True`.
Expect: not verified, and the row's `exit_code != 0`. (#110 also proposes `tampered: true`; assert it once the field is in contracts §2.) Today: exit 0, counted, trained on.

**VF-03 · A skip marker is not verified.** R5 · integration · TODO, **fails on main** (#110)
Agent edit: `@pytest.mark.skip` on the test. pytest exits 0 with `1 skipped`, and `parse_pytest_summary` returns `(0, 0)` (`graduate/reward.py:16-18`).
Expect: not verified. Today: exit 0, `tests_total: null`, counted.

**VF-04 · Changing pytest's configuration is not verified.** R5 · integration · TODO, **fails on main** (#110)
Agent edits, one per case, each checked by hand on 2026-09-27 against `demo-repo` with state 01 planted: (a) a `conftest.py` that patches the function under test (`import calc.mod_01 as m; m.add = lambda a, b: a + b`): pytest prints `1 passed`, exit 0; (b) `addopts = --collect-only` in `pytest.ini`: `1 test collected`, exit 0, parsed as `(0, 0)`.
Expect: each case not verified. Today both count. Control: `addopts = -k nothing` already exits 5 (`1 deselected`) and must stay not verified.

**VF-05 · Deleting the test is already a failure (positive control).** R5 · integration · TODO (should pass on main)
Agent edit: remove the test function. pytest exits 5 ("no tests ran").
Expect: `exit_code == 5` and not verified. Guards against a fix for VF-02–04 that accidentally treats "no tests" as a pass.

**VF-06 · `files_touched_outside_scope` is computed.** R5 · integration · TODO, **fails on main** (C15)
Agent edit: the fix in `calc/mod_01.py` plus a new `notes.txt`.
Expect: the row has `files_touched_outside_scope == 1`; a clean fix gives 0.

**VF-07 · A normal fix still records a clean pass.** R5 · integration · TODO (acceptance box of #110)
Expect: after the #110 fix, the plain fix to `calc/mod_01.py` records `exit 0 · 1/1 passed` and counts.

## LW: ledger, watcher, N (R6)

**LW-01 · The watcher counts the contract's way and flips READY in time.** R6 · integration · exists: `graduate.watcher --check` in `tests/test_selfchecks.py`
Expect: 4 verified, 1 failed, escalation rerun and owned row not counted, `unknown` ignored; the 5th verified row flips READY within 2 s with one `ready` event; replay is idempotent; hand-set title and verify command survive.

**LW-02 · The registry the watcher writes has the contract's shape.** R6 · integration · exists: `tests/test_contracts.py::test_watcher_writes_registry_in_contract_shape`

**LW-03 · The state machine refuses illegal moves and survives concurrent writers.** R6, R7 · integration · exists: `graduate.registry` self-check (`tests/test_selfchecks.py`; 2 × 100 concurrent writes)

**LW-04 · N is configurable end to end.** R6 · e2e offline · TODO (manual evidence: live run at `GRADUATE_N=3`, test report §4)
Setup: ENV-O with `GRADUATE_N=3` exported to both the watcher and the router (each reads it at import, `graduate/registry.py:24`); runs of states 01, 02, 03.
Expect: READY after the 3rd verified row, not before; `/state` `config.n == 3`. The same with `GRADUATE_N=5` stays LEARNING after 3.

**LW-05 · A malformed ledger line doesn't kill the watcher.** R6, R12 · integration · TODO, **fails on main**
Setup: ledger with 4 verified rows, then `not json`, then a 5th verified row; `watch()` in a thread.
Expect: READY within 2 s and the thread still alive. Today `_rows()` raises (`watcher/__init__.py:26`) and the thread dies silently.

**LW-06 · Parallel runners never interleave rows.** R6 · integration · TODO
Setup: 20 processes each calling `ledger.append` with a 50 kB row.
Expect: 20 lines, each parses, each session id once (`ledger.py:10-14`).

**LW-07 · A session whose upstream calls all fail keeps its task type.** R6 · integration · TODO, **fails on main** (#111)
Setup: runner with task hint `fix-failing-test`, stub `fail = (429, …)` for every call.
Expect: the row's `task_type == "fix-failing-test"` and `exit_code != 0`, so `failed_runs` counts it. Today it is `unknown` (`runner:134`).

**LW-08 · A mixed-upstream session is not a verified frontier run.** R6, R8, R13 · integration · TODO, **fails on main** (C14)
Setup: task type GRADUATED; the fake backend raises on the 1st call and answers the 2nd, the 3rd call raises again (frontier serves it); verify passes.
Expect: not verified in the VF sense (`verified_runs` unchanged, absent from `data/<t>.chat.jsonl`). Today `routed_to` is `frontier` (the last call's upstream) and it counts.

## CO: consent honesty (R7)

**CO-01 · The consent screen shows exactly what would be trained, and where.** R7 · integration · exists: `graduate.router.consent` self-check (`tests/test_selfchecks.py`)
Expect: `records == 5`, `tokens == 17`, `sample` equal to line 1 of `data/<t>.chat.jsonl`; `where == "this machine"` without a River key, `river` with one; 404 on unknown names and path traversal; 409 when GRADUATED; revoke sets consent false; Approve returns 202, sets TRAINING and launches the trainer with the task type; no event says River when training is local.

**CO-02 · Revoked consent in PROBATION stops a retrain before anything is sent.** R7 · integration · exists: `tests/test_owned.py::test_revoked_consent_stops_a_retrain_before_anything_is_sent`

**CO-03 · The destination on the screen is the backend the trainer uses.** R7 · integration · TODO (parts exist: `tests/test_owned.py::test_backend_choice`, `tests/test_cli.py::test_up_names_the_owned_backend_and_warns_on_the_river_trap`)
Setup: the four combinations of `RIVER_API_KEY` set/unset × `GRADUATE_OWNED_BACKEND` unset/`local`; plus `none`.
Expect: for each, `GET /api/consent/<t>` `backend` equals `"river"` exactly when `train.backend()` returns `RiverBackend`, and `"none"` when it raises.

**CO-04 · The PROBATION page doesn't promise training on failures.** R7, R18 · visual · TODO, **fails on main** (C4)
Setup: registry with a PROBATION task type, `failed_runs = 2`, a `.neg.jsonl` with 3 lines; open `#/consent/<t>`.
Expect: the page text does not contain "failing runs as examples" (unless the trainer has been changed to read `.neg.jsonl`, in which case the number shown equals `wc -l < data/<t>.neg.jsonl`); the passing-run count shown equals `wc -l < data/<t>.chat.jsonl`. Today it says "plus 2 failing runs as examples of what not to do" (`ui/index.html:519`) while the trainer uses neither.

**CO-05 · A trainer that can't start doesn't strand the task type.** R7, R9 · integration · TODO, **fails on main**
Setup: `consent.TRAIN_CMD = ["/nonexistent"]`; `POST /api/consent/<t>` on a READY type with records.
Expect: a non-2xx response whose body contains `/nonexistent`, and `registry.json` shows READY with no `training` event added. Today the transition happens first (`consent.py:91`) and Popen raises (`:94`), leaving TRAINING.

## DS: dataset correctness and stub isolation (R8, R18)

**DS-01 · Only verified frontier sessions become records.** R8 · integration · exists: `graduate.registrar.dataset --check` (`tests/test_selfchecks.py`, needs `.[train]`, Python 3.12)
Expect: records for the two clean passes only; the escalation rerun, the forced failure and the lost log never become records; the failed owned row is the one negative; `skipped == 1`; weights sum to 1 and fall only on assistant tokens; truncation at `CTX` is counted.

**DS-02 · The chat record matches the contract fixture.** R8 · integration · exists: `tests/test_contracts.py::test_sft_chat_record_matches_fixture`

**DS-03 · Records carry repo-relative paths, in training and serving alike.** R8, R11 · integration · exists: `tests/test_owned.py::test_session_trains_and_serves_with_repo_relative_paths`

**DS-04 · `compare.py` refuses stub data.** R8, R18 · integration · exists: `tests/test_compare.py::test_stub_data_is_refused`

**DS-05 · `compare.py` is deterministic and keeps failed owned rows out of the means.** R16, R18 · integration · exists: `tests/test_compare.py::test_rerun_is_byte_identical`, `::test_failed_owned_row_is_excluded_from_the_means`, `::test_each_arm_prints_its_numbers_and_row_ids`

**DS-06 · A real ledger on the default frontier model isn't mistaken for stub.** R18 · integration · TODO, **fails on main** (C13)
Setup: `tests/compare/ledger.jsonl` rewritten with `model: gpt-5.6-terra`, no `upstream-auth.log` beside it.
Expect: exit 0 and the table printed. Today exit 1 (`scripts/compare.py:22`). Needs a provenance marker that only the stub writes; decide before writing.

**DS-07 · Every training record traces to a verified row (independent).** R8 · independent re-check · TODO
Command: for each line of `data/<t>.chat.jsonl`, find `metadata.session_id` in `ledger.jsonl` and check `routed_to == "frontier"`, `exit_code == 0`, `escalated_from == null`, `forced_failure == false`, and `sessions/<id>.jsonl` exists.
Expect: every record passes; the count equals the consent screen's `records`. One failing record fails the check.

**DS-08 · The demo labels stub numbers in `docs/results.md`.** R18 · e2e offline · TODO
Run: `PORT=4220 scripts/demo.sh --offline --auto-approve` (it starts its own stub on :4221), then `grep -c 'STUB FRONTIER, NOT REAL FRONTIER NUMBERS' docs/results.md`.
Expect: ≥ 1, and every "Change" cell in the generated table reads `n/a: stub frontier`. Restore `docs/results.md` afterwards.

## TR: training (R9)

**TR-01 · Training graduates.** R9 · integration · exists: `tests/test_owned.py::test_train_graduates`

**TR-02 · Failed training goes back to READY.** R9 · integration · exists: `tests/test_owned.py::test_failed_training_goes_back_to_ready`

**TR-03 · A stale TRAINING resets on the next start.** R9 · integration · exists: `tests/test_owned.py::test_stale_training_resets_on_next_start`

**TR-04 · `--use-checkpoint` graduates fast and remembers its run count.** R9 · integration · exists: `tests/test_owned.py::test_use_checkpoint_graduates_in_under_5s`, `::test_checkpoint_remembers_its_run_count_for_use_checkpoint`

**TR-05 · A River model without a key says why and the frontier serves.** R9, R12 · integration · exists: `tests/test_owned.py::test_river_model_without_key_says_why`

**TR-06 · A SIGKILLed trainer doesn't leave TRAINING forever.** R9 · e2e offline · TODO, **fails on main** (#116, PR #123 open)
Setup: ENV-O with the watcher; Approve; `kill -9` the trainer PID once `data/<t>.loss.jsonl` has a line.
Expect: READY and a new event within one watcher poll after the kill (PR #123's bar; `POLL_SECS` is 1 s, so assert within 3 s), without any training run being started. Today: TRAINING until another trainer starts.

**TR-07 · SIGTERM returns to READY.** R9 · integration · TODO
Setup: a subprocess that sets `graduate.registrar.train.backend` to return an object whose `train` sleeps 60 s, then calls `train.run("<t>")` on a TRAINING task type with records; send it SIGTERM after 2 s.
Expect: process exits non-zero within 5 s; state READY; newest event `error` containing `killed` (`train.py:387-389,453-463`).

**TR-08 · A real local training run learns something.** R9 · e2e offline, ENV-H · TODO (manual evidence: attempt 2, test report §4)
Run: `graduate train fix-failing-test --steps 15` on a dataset of ≥ 3 real sessions.
Expect: exit 0; `data/<t>.loss.jsonl` has 15 rows, last loss < first loss / 2; `data/checkpoints/<t>-v<n>/adapter_config.json` and `graduate.json` exist; registry GRADUATED with `trained_on_runs` equal to the record count; `peak_rss_mb` in every row (record the max).

## RO: routing to the owned model (R10, R11, R12)

**RO-01 · Owned streams are OpenAI SSE with tool calls.** R11 · integration · exists: `tests/test_owned.py::test_owned_stream_is_openai_sse_with_tool_calls`

**RO-02 · Owned JSON, and no usage chunk unless asked.** R11 · integration · exists: `tests/test_owned.py::test_owned_json_and_no_usage_chunk_unless_asked`

**RO-03 · An owned model that's down falls back to the frontier.** R12 · integration · exists: `tests/test_owned.py::test_owned_model_down_falls_back_to_frontier` (stream and JSON)

**RO-04 · PROBATION sends the next call to the frontier, no restart.** R10, R14 · integration · exists: `tests/test_owned.py::test_probation_sends_the_next_call_to_the_frontier`

**RO-05 · GRADUATED without a model goes to the frontier.** R10 · integration · TODO
Setup: registry GRADUATED with `model: null`.
Expect: the stub serves; the fake backend is never called (`route.py:43`).

**RO-06 · Owned generation is deterministic.** R11 · e2e offline, ENV-H · TODO
Setup: the shipped checkpoint; one fixed `messages` list from a session log.
Expect: `LocalBackend().complete(...)` twice returns identical `content` and `tool_calls` (ids excluded; they embed a timestamp, `train.py:108`). A difference means greedy decoding (`train.py:275`) isn't what runs, and EV-02 must use repetitions.

## PA: parsing the owned model's tool calls (R11)

**PA-01 · Qwen text becomes OpenAI tool calls, `</tool_call>` opener included.** R11 · unit · exists: `tests/test_owned.py::test_parse_qwen_tool_calls`
Expect: `<think>` stripped; a malformed call dropped; the `</tool_call>` opener (#107) parsed.

**PA-02 · The compact prompt keeps the env block and the task's tools.** R11 · unit · exists: `tests/test_owned.py::test_compact_keeps_env_and_task_tools`

**PA-03 · A real checkpoint's first answer reaches OpenCode as a tool call.** R11 · e2e offline, ENV-H · TODO (manual evidence: independent audit, test report §5)
Setup: ENV-O, task type graduated on the shipped checkpoint with `graduate train fix-failing-test --use-checkpoint <dir>`; run state 07.
Expect: `sessions/<id>.jsonl` line 2 or later has `upstream: owned` and a non-empty `response.tool_calls`; OpenCode's output shows the tool ran. 0 tool calls across the session fails.

## ES: escalation (R13)

**ES-01 · Failed owned sessions reset, rerun on the frontier, and are kept.** R13, R14 · integration · exists: `graduate.escalator` self-check (`tests/test_selfchecks.py`)
Expect: each forced failure gives a failed row plus a linked passing rerun (`escalated_from`); the rerun starts from the planted bug; files outside the repo survive; PROBATION on the 3rd failure; a real owned failure is kept as one negative and its failing rerun is not escalated again.

**ES-02 · Escalating into a rate-limited frontier doesn't burn a full session.** R13 · integration · TODO, **fails on main** (#111)
Setup: GRADUATED task type, owned attempt fails verify, then the stub answers every call 429.
Expect: the rerun row exists with `escalated_from` set, `exit_code != 0` and `wall_secs < 10`, and an event or terminal line names 429. Today the rerun runs a whole OpenCode session.

**ES-03 · The same for an auth failure.** R13 · integration · TODO, **fails on main** (#111)
As ES-02 with 401.

**ES-04 · An escalation that raises still leaves the failed row.** R12, R13 · unit · TODO
Setup: monkeypatch `escalator.escalate` to raise.
Expect: `runner.run` returns the failed owned row; the ledger has exactly that one row; stdout contains `escalation failed` (`runner:176-179`).

## PB: probation (R14)

**PB-01 · The fail limit is configurable.** R14 · integration · TODO
Setup: a subprocess (both modules read the variable at import) with `GRADUATE_FAIL_LIMIT=1`; one forced failure, as in the escalator self-check.
Expect: PROBATION after the first failure; `/state` `config.fail_limit == 1`. (Both modules read it at import: `escalator:22`, `state.py:15`.)

**PB-02 · A retrain from PROBATION resets the counters.** R14, R9 · integration · TODO
Setup: PROBATION with `failures_since_graduation = 3`; Approve with a fake backend.
Expect: GRADUATED, `failures_since_graduation == 0`, `verified_since_graduation == 0`, `graduated_at` newer than before, checkpoint `v<n+1>` (`train.py:414,435-445`).

**PB-03 · A healthy GRADUATED type can't be sent to training.** R7, R14 · integration · exists: consent self-check (409 on `update-changelog`, GRADUATED)

## UI: dashboard (R15)

**UI-01 · The router serves every dashboard asset.** R15 · integration · exists: `tests/test_ui.py::test_router_serves_every_local_ui_asset`

**UI-02 · `graduate results` freezes `/state`.** R15 · integration · exists: `tests/test_ui.py::test_results_freezes_the_dashboard_state`

**UI-03 · Compare before any bench is not a server error; the latest bench is served.** R15 · integration · exists: `tests/test_ui.py::test_compare_before_any_bench_is_not_a_server_error`, `::test_router_serves_the_latest_bench_for_compare`

**UI-04 · Fixture state is labelled sample data.** R15, R18 · integration · exists: `tests/test_ui.py::test_demo_router_says_its_numbers_are_sample_data`

**UI-05 · `/state` totals are computed from the ledger.** R15, R16 · integration · exists: `graduate.router.state` self-check (`saved_usd == 0.4174` from the fixtures; a bad ledger line is skipped; no registry → zeros)

**UI-06 · Projector layout: no overflow, no console errors, legible text.** R15 · visual · exists as `make screens` (`scripts/screens.py`), not in CI
Run: `pip install playwright && playwright install chromium && make screens`
Expect: exit 0; fails on console errors, failed requests, horizontal overflow, cut-off views, text under `innerHeight/45`, wrong 5-of-5 counts, owned numbers for an ungraduated type, missing sample label.
Edge: covers show, compare, overview-present, system-present at 1920×1080 and 1280×720 only.

**UI-07 · Every view is console-clean after a real run.** R15 · visual · TODO (manual evidence: 9 views, 02-smoke)
Setup: after E2-02, a headless browser on `/`, `?present`, `#/show`, `#/compare`, `#/system`, `#/setup`, `#/task/fix-failing-test`, `#/consent/fix-failing-test`.
Expect: zero `console.error` and `console.warning` entries and zero failed requests on every view; each view's main container is non-empty.

**UI-08 · Numbers on screen equal numbers recomputed from the ledger.** R15, R16 · independent re-check + visual · TODO (manual evidence: independent audit §5)
Command: recompute from `ledger.jsonl` and `registry.json` alone: per task type `verified_runs`, `failed_runs`, baseline means, and `saved_usd` (Σ over owned exit-0 rows of `baseline.cost_usd − cost_usd`); read the same numbers from the rendered Overview and Showcase.
Expect: all equal (money to the cent shown). A hard-coded or stale number fails.

**UI-09 · A registry change reaches the screen within a second.** R15 · visual · TODO (manual evidence: 530 ms; the page polls `/state` every 1 s, `ui/index.html:645`)
Setup: dashboard open; `registry.update(<t>, title="Changed")` at t0.
Expect: the new title is in the DOM by t0 + 1.5 s.

**UI-10 · A lost router shows "Reconnecting…" and recovers.** R15 · visual · TODO (manual evidence)
Setup: block `/state` (route interception) for 5 s, then unblock.
Expect: `#conn` reads "Reconnecting… showing the last state" while blocked (`ui/index.html:404`); the text is gone within 2 s of unblocking.

## MC: MCP server (R17)

**MC-01 · The tools report what `/state` reports.** R17 · integration · exists: `tests/test_mcp.py::test_stdio_tools_match_state`

**MC-02 · Bad lines get errors and the server keeps serving.** R17 · integration · exists: `tests/test_mcp.py::test_bad_lines_get_errors_and_the_server_keeps_serving`

**MC-03 · A real MCP client calls both tools.** R17 · e2e offline · TODO (manual evidence: 02-smoke/mcp29)
Setup: `claude mcp add graduate -- python -m graduate.mcp` in a directory with a ledger and registry; ask for status and savings.
Expect: the client's transcript shows both tool calls and their numbers equal `/state` `registry` counts and `totals`.

## AM: Anthropic `/v1/messages` (R19)

**AM-01 · Claude Code's streaming calls go through the same path.** R19 · integration · exists: `tests/test_router.py::test_claude_code_messages_stream_through_the_same_path`
Expect: `tool_use` blocks with ids and names, argument deltas, `stop_reason: tool_use`, Anthropic usage (`input_tokens` excludes cached); the frontier got `system, user, assistant, tool`; `user` is the prompt id; 400 `invalid_request_error` on four bad bodies.

**AM-02 · Non-streaming `/v1/messages` returns an Anthropic message.** R19 · integration · TODO
Expect: `type: message`, text and `tool_use` content blocks, `stop_reason` `end_turn` / `tool_use` / `max_tokens` from `stop` / `tool_calls` / `length` (`anthropic.py:12,72-88`).

**AM-03 · An upstream error comes back in Anthropic's error envelope.** R19 · integration · TODO
Setup: stub `fail = (429, …)`.
Expect: status 429, body `{"type": "error", "error": {"type": "api_error", …}}` (`anthropic.py:163-167`).

**AM-04 · The real `claude` CLI works through the router.** R19 · e2e offline · TODO (manual evidence: test report §3e)
Setup: ENV-O; `ANTHROPIC_BASE_URL=http://localhost:4210 ANTHROPIC_API_KEY=sess-<12 hex> claude -p "<prompt>"`, once plain and once for a task needing 3 tool calls.
Expect: both complete with exit 0; `sessions/sess-<id>.jsonl` has one line per model call, and the tool session has ≥ 3 `tool_calls` across its responses.
Edge: with Claude Code's own non-`sess-` key, the lines land in `sess-anon` and the session is never owned-routed (C12; SI-03 asserts that current behaviour until the owner decides otherwise).

## GB: GBrain (R17)

**GB-01 · Graduation writes `GRADUATED.md` and fails open.** R17 · integration · exists: `tests/test_gbrain.py::test_graduation_writes_graduated_md_and_fails_open`

**GB-02 · A malformed registry entry doesn't break graduation.** R17 · integration · exists: `tests/test_gbrain.py::test_graduation_survives_a_malformed_registry_entry`

**GB-03 · A real brain holds the same page.** R17 · e2e offline · TODO (manual evidence: test report §3d)
Setup: `gbrain init --pglite --no-embedding` in a scratch brain; graduate a task type; then demote it to PROBATION.
Expect: `gbrain get graduated` equals `GRADUATED.md` byte for byte after each transition. With no brain: the transition completes in < 1 s.

## ME: Memorable (R17)

**ME-01 · The trace sent to Memorable carries only allow-listed data.** R17, R2 · unit · TODO
Setup: a session log whose tool calls have `file_path`, `content`, `oldString`, `command`.
Expect: `build_trace` inputs contain only `command, file_path, path, pattern, url, query` keys; no tool output; the last entry is the verify command with the real exit code; `task_description` ≤ 200 chars (`bridge.py:10,37-58`).

**ME-02 · Only passing frontier sessions are ingested.** R17 · integration · exists: asserted in `tests/test_runner.py::test_run_verifies_and_appends_one_ledger_row`

**ME-03 · Ingest writes the slug map that classification reads.** R4, R17 · integration · TODO
Setup: `MEMORABLE_BIN` = a script printing `fixtures/memorable/ingest-trace-fix-failing-test-05.txt`.
Expect: `data/slug_map.json` maps the printed slug to the task type; a following CL-03-style recall of that slug classifies to the same task type.

**ME-04 · Real Memorable recall finds a stored procedure.** R4, R17 · e2e live (Memorable account) · TODO (manual evidence: test report §3c)
Expect: `memorable recall "<state 08 prompt>" --single` returns a `procedures/…` slug with score ≥ 0.6.

## CM: cost math (R16)

**CM-01 · Per-call cost follows contracts §9 and sums per session.** R16 · integration · exists: `graduate.router.metrics` self-check (cost of every fixture row, exact per-call costs, aggregate equals the file's sum)

**CM-02 · Budget caps stop spending.** R16 · integration · exists: `tests/test_bench.py` (cap, mid-run watchdog, dry run, no key), `tests/test_corpus.py::test_corpus_caps_stop_the_next_session_and_a_runaway_one`, `tests/test_e2e.py`

**CM-03 · The caching-on baseline is cheaper than the uncached price.** R16 · unit · TODO
Setup: one frontier usage `{input 10000, cached 8000, output 100}`.
Expect: `metrics.cost(usage, "frontier") == (2000×2.0 + 8000×0.2 + 100×12.0)/1e6 == 0.0068` with `fixtures/prices.example.json`, strictly less than the uncached `(10000×2.0 + 100×12.0)/1e6`.

**CM-04 · Every live ledger cost recomputes exactly (independent).** R16 · independent re-check · TODO (manual evidence: test report §4, "exact")
Command: for each row, sum `usage` over `sessions/<id>.jsonl`, price with `prices.json`, compare to `cost_usd`.
Expect: every |difference| < 1e-6.

**CM-05 · Owned cost is shown on both bases.** R16, R18 · integration · exists: `tests/test_compare.py::test_each_arm_prints_its_numbers_and_row_ids` (River list price and local $0 plus training wall time)

## LV: live account limits

**LV-01 · No key: skip after the estimate, spend nothing.** integration · exists: `tests/test_e2e.py::test_no_key_skips_after_the_estimate`

**LV-02 · One 1-token probe, and no session unless it answers.** integration · exists: `tests/test_e2e.py::test_one_1_token_probe_and_no_session_unless_it_answers`

**LV-03 · `live.sh` refuses without credit before touching anything.** R20 · integration · exists: `tests/test_e2e.py::test_live_sh_refuses_without_credit_before_touching_anything` (fails on macOS, #120: MAC-01)

**LV-04 · Request headroom is checked before a live run.** e2e live · TODO
Command: one 16-token request to the chosen model, read `x-ratelimit-remaining-requests` and `x-ratelimit-limit-tokens`.
Expect: the run starts only if remaining requests ≥ planned calls (about 60 for the demo) and the token limit per minute ≥ the largest request (11k tokens was measured for one OpenCode turn). Otherwise it refuses and prints both numbers.

**LV-05 · A live session passes and costs what the tokens say.** R1, R5, R16 · e2e live · TODO (manual evidence: 3 gpt-5-mini sessions, test report §4)
Setup: ENV-L, state 01.
Expect: exit 0; `turns ≥ 2`; ledger `cost_usd` equals CM-04's recomputation; in `sessions/<id>.jsonl` at least one call after the first has `usage.cached_input_tokens > 0` (caching on, as the baseline assumes).

## MAC: macOS portability (R20)

**MAC-01 · `live.sh` starts on macOS.** R20 · integration · exists: LV-03's test, **fails on macOS** (`scripts/live.sh:17` uses GNU `realpath -m`, #120)
Expect: passes on the demo Mac.

**MAC-02 · The whole suite passes on macOS.** R20 · integration · TODO, **fails on main** on macOS
Run: ENV-U on the demo Mac, `make check && make test`.
Expect: 0 failed. Today, on the build Mac at `e723076` with no `OPENAI_*`, `RIVER_*` or `GRADUATE_*` variables set: 104 passed, 3 failed (MAC-01, `tests/test_bench.py::test_bench_runs_each_arm_on_its_own_model` and `::test_owned_arm_takes_the_graduated_route`). The test report saw only MAC-01 at `55455c6`; find out why the bench tests fail here before the demo.

**MAC-03 · The offline demo completes on macOS.** R20 · e2e offline · TODO (manual evidence: test report §3a on an M4)
Run: `PORT=4220 scripts/demo.sh --offline --auto-approve` on the demo Mac.
Expect: a `demo ok` line, exit 0. CI has no macOS runner, so this is a release gate run by hand.

## E2: the full loop

**E2-01 · Real OpenCode on the stub, replayed.** R1–R6 · e2e offline · exists: `make e2e-replay` (CI job `e2e-replay`)

**E2-02 · The whole demo from a clean checkout.** R1–R14 · e2e offline · exists: CI job `demo-offline` (`scripts/demo.sh --offline --auto-approve --use-checkpoint …`)
Expect: `demo ok`, exit 0. `demo.sh` dies unless the task type reaches each state in time (`scripts/demo.sh:50-56`) and the last two ledger rows are an owned exit 1 and a frontier exit 0 whose `escalated_from` is the owned row's id (`scripts/demo.sh:187`).

## EV: held-out eval protocol (R11, R13, R18)

The protocol behind any "the owned model fixes new instances" claim (#112, #117). Runs in ENV-O for the owned side: the owned model is real, and only owned rows are measured, so the stub frontier doesn't distort the result.

1. **Split.** Train states and eval states are fixed before training and written in the report. Default (#112): train 01–05, eval 06–10. The shipped checkpoints trained on 01–08, so with them only 09 and 10 are eval states.
2. **Train.** `graduate train fix-failing-test` on the train-state sessions only (ENV-H), or name the checkpoint and its training states.
3. **Evaluate.** For each eval state and each repetition: `scripts/reset-demo.sh NN`, then `graduate run --task-file demo-repo/tasks/NN.json --repo demo-repo`, with `GRADUATE_FAIL_LIMIT=1000` in the runner's environment so an early failure can't put the type on probation mid-eval (the test report reset the counter by hand instead).
4. **Score.** An eval run passes when its first ledger row has `routed_to: owned` and `exit_code: 0`. A first row with `routed_to: frontier` is a fail and is flagged: the owned path errored and the frontier finished the session (C14). The escalation rerun that follows a failure is never counted.
5. **Report.** A table of state × repetition with session ids, then pass@1 per state and overall, produced by a command from `ledger.jsonl`.

**EV-01 · No train/eval overlap.** R18 · independent re-check · TODO
Command: map each `metadata.session_id` in `data/<t>.chat.jsonl` to its ledger `prompt`, extract `test_mod_(\d\d)`.
Expect: the set of training states and the set of eval states are disjoint. Any overlap voids the table.

**EV-02 · Repeatability.** R18 · e2e offline, ENV-H · TODO
Expect: 3 repetitions per eval state; with greedy decoding (RO-06) every repetition of a state has the same outcome. A state whose outcomes differ is reported as such, with its rate, never as its best repetition.

**EV-03 · Held-out pass@1 on the stub-trained checkpoint.** R11 · e2e offline, ENV-H · TODO (#112)
Expect: a committed table, states 06–10 (or 09–10 on the shipped checkpoints) × 3, with the command that produced it from `ledger.jsonl`; re-running that command on the same ledger prints the same table.

**EV-04 · The real-data bar.** R11 · e2e live data, ENV-H · TODO (#117; blocked on #114 for ≥ 5 real sessions)
Expect: a model trained on real frontier sessions of the train states passes ≥ 3 of 5 eval states at pass@1. Today 1 of 7.

**EV-05 · Fewer turns and lower cost, or not.** R16, R18 · e2e live · TODO (#118)
Run: `python scripts/compare.py ledger.jsonl` on a real ledger.
Expect: the verdict line (`fewer turns: yes/no … lower cost: …`) is quoted as printed, both cost bases shown; `compare.py` exits 1 on stub data.

**EV-06 · Independent re-run.** R18 · independent re-check · TODO
Setup: someone who didn't produce EV-03 clones at the named commit, takes the named checkpoint and runs steps 3–5.
Expect: the same pass/fail per state and repetition. Any difference is reported next to the original table.

---

## Requirements intake

When the organizers' requirements arrive, turn each one into rows here before writing any code.

1. **Quote it.** Copy the requirement verbatim with its source (URL, message, slide) and a short id `ORG-<n>`.
2. **Map it** to one or more of R1–R20. If none fits, add `R21+` to [PRODUCT.md](PRODUCT.md#requirements) in the same PR.
3. **Find the tests** above whose "R" list includes those ids. For each, say whether the organizer's wording is already what the test's "Expect" asserts. If the wording is stricter (a number, a latency, a named harness), write a new test or tighten the existing one's "Expect"; never loosen one to fit.
4. **Decide the level.** A requirement about judged output (a demo, a number on a slide) needs at least one e2e test and one independent re-check. A requirement about safety or honesty needs a test that fails on the dishonest version.
5. **Check it can fail.** Write down the smallest change to the code that would make the test fail. If there isn't one, the test proves nothing: rewrite it.
6. **Check the budget.** ENV-L tests list their expected calls and dollars; sum them against the account's remaining requests (LV-04) before promising a live result.
7. **Record the status** in the table below and in the summary counts.

Template (one per organizer requirement):

```
ORG-<n>: "<verbatim requirement>" (source: <link>)
Maps to: R<x>, R<y>
Tests: <ID> (exists | TODO | TODO, fails on main), ...
New or tightened: <ID> · <level> · Setup: ... · Run: ... · Expect: ... · Edge: ...
Fails if: <the smallest code change that breaks it>
Budget: <$ and requests for ENV-L tests, or $0>
Owner / issue: #<n>
```

| ORG id | Requirement (short) | R ids | Tests | Status |
|---|---|---|---|---|
| | | | | |
