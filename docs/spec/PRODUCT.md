GRADUATE: product specification
===============================

What GRADUATE does, who it is for, the lifecycle every task type goes through, what it will not do, and what may be claimed about it. Every statement about current behaviour cites the code (`file:line`, on `main` at `e723076`). Which source wins when docs and code disagree is stated once, in [ARCHITECTURE.md § Source of truth](ARCHITECTURE.md#source-of-truth).

Companion files: [ARCHITECTURE.md](ARCHITECTURE.md) (components, data flow, failure modes, tradeoffs) and [TEST-PLAN.md](TEST-PLAN.md) (the acceptance tests, keyed to the requirement ids below).

Canonical sources this file does not repeat:

| Topic | Canonical doc |
|---|---|
| Every shape that crosses a component boundary (ledger row, session log, registry, dataset, trace, cost formula) | [`graduate/contracts.md`](../../graduate/contracts.md) |
| The pitch, the Harvey precedent, the RL reward rationale | [`02-project/graduate-spec.md`](../../02-project/graduate-spec.md) §1–§2c, §5 |
| Decided stack, working rules, owned-model claim rules | [`AGENTS.md`](../../AGENTS.md) |
| What was measured today, with raw evidence | the test report (`Jelly-test-report/README.md`, outside the repo) and [`docs/results.md`](../results.md) |

## Purpose

A coding agent pays frontier prices to redo the same kind of task every time. GRADUATE sits between the agent and its model as an OpenAI-compatible proxy. It records every session, verifies each one by the exit code of the task's test command, and once a task type has N verified frontier sessions and the owner approves, trains a small model the owner keeps on those sessions and routes that task type to it. Every owned session is still verified; a failure is rerun on the frontier and kept.

## Users

| User | What they need from GRADUATE |
|---|---|
| A developer running a coding agent (OpenCode today; Claude Code through `/v1/messages`) against a repo with a real test suite | One setting change (`baseURL`), no change to how they work, and never a worse result than the frontier alone |
| The owner of the training data (the same person, or their team lead) | To see exactly which sessions would be trained on and where they would go, and to say yes or no per task type |
| A judge or reviewer | Numbers that trace to raw rows, with stub, repeat and held-out results labelled as such |

## Requirements

Each requirement has an id. [TEST-PLAN.md](TEST-PLAN.md) proves each one; a new organizer requirement is mapped onto these ids first (TEST-PLAN § Requirements intake).

| Id | Requirement |
|---|---|
| R1 | Passthrough: a Chat Completions client pointed at the router gets the frontier's status and body unchanged, streamed as it arrives |
| R2 | Session identity: the bearer `sess-<12 hex>` is the session id; it never goes upstream, and the upstream key never reaches the agent or the disk |
| R3 | Recording: every successful model call writes one session-log line and one metrics line; a failed upstream call writes neither |
| R4 | Classification: every session gets exactly one task type, fixed for the session |
| R5 | Verification: every session is verified by its task's command after the agent exits, and the exit code is the only label |
| R6 | Counting: `verified_runs` counts frontier sessions with exit 0 that are not escalation reruns; the task type becomes READY at N |
| R7 | Consent: nothing trains without an explicit approval, and the approval screen shows the exact records, their count and token total, and where they go |
| R8 | Dataset: only verified frontier sessions become training records; stub data never feeds a real claim |
| R9 | Training: success graduates the task type with a checkpoint; failure returns it to READY and says why |
| R10 | Routing: a GRADUATED task type's calls go to the owned model; every other state goes to the frontier |
| R11 | Owned output is OpenAI-shaped, tool calls included, so the agent cannot tell the difference in format |
| R12 | Fail open: any error on the owned path ends with the frontier serving |
| R13 | Never trust the small model: a failed owned session resets the repo, reruns on the frontier, and is kept |
| R14 | Probation: repeated owned failures stop owned routing until a consented retrain |
| R15 | Dashboard: every view renders the registry and ledger truthfully, with no console errors |
| R16 | Cost: contracts §9, with a caching-on frontier baseline |
| R17 | Integrations (Memorable, GBrain, MCP) are optional and fail open |
| R18 | Honesty: every claim is labelled with what it rests on (see Honesty rules) |
| R19 | Claude Code can use the router through Anthropic `/v1/messages` |
| R20 | Portability: the demo path runs on macOS (the demo machine) and Linux (CI) |
| R21 | After graduation, the task type's sessions take fewer turns and tool calls than its caching-on frontier baseline, with the result still verified (graduate-spec §8 criterion 2; the #118 bar) |

## The lifecycle

The states, the diagram and the legal-transition table are in [contracts §1](../../graduate/contracts.md#1-states-and-transitions) (the pitch version is [graduate-spec §4](../../02-project/graduate-spec.md#4-the-graduation-lifecycle)); the code's table is `graduate/registry.py:40-59`, and any other move raises `IllegalTransition` (`graduate/registry.py:134-136`). This section adds, per transition, what triggers it in the running system, what it guarantees, and what happens when it fails.

| Transition | Trigger (code) | Guarantee | Failure behaviour |
|---|---|---|---|
| none → LEARNING | The watcher's scan meets a ledger row whose `task_type` isn't `unknown`; `registry.update` creates the entry as LEARNING (`graduate/watcher/__init__.py:39`, `graduate/registry.py:171`) | `unknown` rows never create a task type (`graduate/watcher/__init__.py:39`) | Without a running watcher nothing is created. `graduate up` starts one (`graduate/cli.py:213-216`) and `scripts/demo.sh:89` starts one; a bare `uvicorn` router does not, and `scripts/live.sh:57` scans once |
| LEARNING → READY | Watcher polls `ledger.jsonl` mtime every 1 s (`graduate/watcher/__init__.py:15,114-120`) and flips when `verified_runs >= GRADUATE_N` (`:85-95`). N defaults to 5 (`graduate/registry.py:24`) | The registry itself refuses READY below N (`graduate/registry.py:139-146`). Escalation reruns, owned rows and failed rows don't count (`graduate/watcher/__init__.py:51-54`). Replaying the ledger is idempotent (watcher self-check) | A malformed ledger line other than a half-written last one raises in `_rows()` (`graduate/watcher/__init__.py:26`), and `watch()` has no handler, so the watcher thread dies and nothing flips again until restart. READY does **not** build the dataset |
| READY → TRAINING | `POST /api/consent/<task_type>` (`graduate/router/consent.py:78-96`), or `graduate train <task_type>` by hand, which transitions only if consent is already true (`graduate/registrar/train.py:382-386`, `graduate/registry.py:147-148`) | Approve refuses with 409 unless the state is READY or PROBATION (`consent.py:83-84`) and `data/<t>.chat.jsonl` has records (`consent.py:85-87`). Consent is set, then the state moves, then the trainer is launched detached (`consent.py:88-94`) | The dataset must already be built by `python -m graduate.registrar.dataset <t>` (`scripts/demo.sh:115` does it; nothing else does). If the trainer can't be spawned after the transition (`consent.py:91` before `:94`), the task type is left in TRAINING with no trainer |
| TRAINING → GRADUATED | The trainer saves a checkpoint (`graduate/registrar/train.py:435-445`), or `--use-checkpoint` points at an existing adapter (`train.py:392-403`) | Same write sets `model`, `serving: checkpoint`, `trained_on_runs`, `graduated_at`, and resets `verified_since_graduation` and `failures_since_graduation` to 0 (`train.py:435-445`). GBrain publish runs after (`graduate/registry.py:159-163`) and can't block it (`graduate/gbrain.py:36-37`) | Any Python exception, and SIGTERM (`train.py:387-389`), sends it back to READY with an `error` event (`train.py:453-463`) |
| TRAINING → READY | Trainer failure (above), or `reset_stale()` finding a TRAINING whose `training` event is over an hour old (`train.py:341-360`) | The frontier keeps serving throughout: only GRADUATED routes to the owned model (`graduate/router/route.py:43`) | `reset_stale()` runs only when a trainer starts (`train.py:378`). A trainer killed by SIGKILL or the OOM killer leaves TRAINING until some later training run starts (#116; PR #123 open) |
| GRADUATED (steady) | Router routes the task type's calls to the owned model (`route.py:43`, `graduate/router/river.py:46-123`) | Every owned session is verified by the runner (`graduate/runner/__init__.py:115`). An owned call that errors is served by the frontier (`river.py:60-75`) | Per call, not per session: a session can mix owned and frontier calls, and its ledger `routed_to` is the upstream of its **last** call (`graduate/runner/__init__.py:51,131`) |
| GRADUATED → PROBATION | The escalator, after a failed owned session, when `failures_since_graduation >= GRADUATE_FAIL_LIMIT` (default 3) (`graduate/escalator/__init__.py:22,92-114`). graduate-spec §4 says one failure demotes; the code needs three (C16) | Forced demo failures count too (`escalator/__init__.py:91-95`). The next call goes to the frontier without a router restart (registry re-read on mtime, `route.py:18-26`) | There is no owner "demote" action in the code, although contracts §1 names one |
| PROBATION → TRAINING | `POST /api/consent/<t>` again (`consent.py:13,83`), or `graduate train <t>` by hand while consent is still true from the first approval (`train.py:382-386`) | Consent can still be revoked in PROBATION and holds (`consent.py:99-108`; `tests/test_owned.py::test_revoked_consent_stops_a_retrain_before_anything_is_sent`) | The retrain trains on `data/<t>.chat.jsonl` only (`train.py:405-413`): negatives in `.neg.jsonl` are kept but **not** trained on, so "retrain includes the negatives" (contracts §1) is not what happens |

No path exists from GRADUATED straight to TRAINING (a retrain of a healthy model) or from PROBATION back to GRADUATED.

## Non-goals

- **Codex and the Responses API.** The router speaks `/v1/chat/completions` and `/v1/messages` only (`graduate/router/app.py:113`, `graduate/router/anthropic.py:146`).
- **Per-call verification.** Verification is per session, after the agent exits (`graduate/runner/__init__.py:115`). A call is never judged on its own.
- **A learned or embedding classifier.** Classification is the runner's task-type hint, else Memorable recall mapped through `data/slug_map.json`, else a slug built from the normalized prompt (`graduate/router/classify.py:46-64`).
- **Multi-user auth.** The bearer is a session id, not a credential; the router trusts whoever can reach its port (binds 127.0.0.1 by default, `graduate/cli.py:236`).
- **A database.** `registry.json`, `ledger.jsonl`, `metrics.jsonl`, `sessions/`, `data/`, `trace.jsonl`, all local files.
- **RL training in the product loop.** The exit-code RL spike exists (`graduate/rl_env.py`, [`docs/river-rl.md`](../river-rl.md)) and is not wired to graduation.
- **Windows.** Registry and ledger locking use `fcntl` (`graduate/registry.py:14`, `graduate/ledger.py:3`).
- **Training during a live demo.** The demo graduates on a checkpoint trained beforehand (`--use-checkpoint`) and says so ([SUBMISSION.md](../../SUBMISSION.md#honest-limits)).

## Honesty rules

The rules for what may be claimed are in [AGENTS.md](../../AGENTS.md) ("Owned-model claims" and "Honesty"), [`03-build/risks.md`](../../03-build/risks.md) §8 and [SUBMISSION.md § Honest limits](../../SUBMISSION.md#honest-limits). They are canonical; this file doesn't copy them. Three rules follow from the code and are not written down anywhere else:

- **Name the training backend actually used.** Say "on River" only when `RiverBackend` trained it. The consent screen and the events name the backend `train.backend()` picks (`graduate/router/consent.py:18-25`).
- **Say which price basis an owned cost uses.** Owned rows are priced at the `owned` block of `prices.json` (River list prices) even when the model ran on local CPU at $0 marginal (`graduate/router/metrics.py:73`). `scripts/compare.py` prints both bases.
- **Don't present the demo's task type as learned.** In the demo the task type comes from the task file's `task_type` (`demo-repo/tasks/*.json`, `graduate/router/classify.py:49-50`), not from Memorable.
