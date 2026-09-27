# Jelly: results (#31)

## Real runs (Claude Haiku 4.5 as the big model)

**Real, 2026-09-27 22:08–22:46Z.** OpenAI had no credit, so the big model is **Claude Haiku 4.5** (`claude-haiku-4-5`), called through Anthropic's OpenAI-compatible Chat Completions endpoint (`OPENAI_BASE_URL=https://api.anthropic.com/v1`). The router needed no code change. Prices: `fixtures/prices.claude.json`, Anthropic list $1 per 1M input tokens, $5 per 1M output. Every session is a real OpenCode run through the router, verified by the task's own pytest command. Nothing in this section comes from the stub.

**Caching is off on this path.** Anthropic's compatible endpoint reports no cached tokens (`cached_input_tokens` 0 on every call), so every input token is billed at the full rate. The frontier cost below is higher than a cached baseline would be. Output tokens and turns don't depend on caching.

**The big model on broken states 01–08** (`scripts/corpus.sh`, capped at 100 calls / USD 2.00): 8 of 8 verified.

| State | Session | Turns | Tool calls | Input tokens | Output tokens | Cost | Wall (s) | Verify |
|---|---|---|---|---|---|---|---|---|
| 01 | `sess-e778387f1cb0` | 8 | 7 | 196,807 | 763 | $0.2006 | 19.7 | exit 0 |
| 02 | `sess-4679b2b91a3e` | 7 | 7 | 170,786 | 774 | $0.1747 | 19.1 | exit 0 |
| 03 | `sess-485741aec4da` | 7 | 6 | 168,374 | 650 | $0.1716 | 17.2 | exit 0 |
| 04 | `sess-58bc4c439302` | 7 | 7 | 170,017 | 763 | $0.1738 | 17.1 | exit 0 |
| 05 | `sess-046f6bb2c3b9` | 6 | 6 | 140,867 | 651 | $0.1441 | 14.9 | exit 0 |
| 06 | `sess-dd2e683296e0` | 7 | 6 | 168,375 | 644 | $0.1716 | 18.2 | exit 0 |
| 07 | `sess-037de8e19457` | 7 | 6 | 168,994 | 734 | $0.1727 | 18.7 | exit 0 |
| 08 | `sess-f61f363e6a5c` | 8 | 6 | 196,142 | 703 | $0.1997 | 21.7 | exit 0 |

Mean per session: 7.1 turns, 6.4 tool calls, 710 output tokens, $0.176, 18.3 s.

**The owned model, retrained on those 8 real sessions.** Qwen2.5-Coder-0.5B with LoRA, trained on this machine's CPU: 24 steps, loss 2.07 → 0.12, 1171.5 s, peak 4.6 GB (checkpoint `fix-failing-test-claude-v1`). It was then evaluated through the same router and runner, served locally at $0. A failed owned session escalates, and the escalator reruns it on Claude.

| State | Kind | Owned session | What the owned model did | Turns | Output tokens | Wall (s) | Verify | Frontier rerun |
|---|---|---|---|---|---|---|---|---|
| 07 | repeat (in training) | `sess-f805428cb504` | `"aeio"` → `"aeiou"`, the right fix | 6 | 326 | 125.7 | **exit 0** | none needed |
| 09 | held out | `sess-9b43f23d9bda` | two `edit` calls missing `newString`, both rejected | 7 | 357 | 252.5 | exit 1 | `sess-f503244eee3e`, exit 0, 6 turns, $0.1441 |
| 10 | held out | `sess-78d154d1ef86` | removed the `10 *` instead of making it `100 *` | 6 | 315 | 234.0 | exit 1 | `sess-bd968b5c0688`, exit 0, 5 turns, $0.1151 |

**The owned model still fails both held-out states.** It passes the one repeat, 07, which is in its training data. That pass shows it learned the agent loop and the tool calls; it doesn't show that it generalizes. Both held-out failures escalated, and Claude fixed them, so the user got a passing result every time.

`python scripts/compare.py ledger.jsonl --prices fixtures/prices.claude.json` on the real ledger (13 rows), verbatim:

```
fix-failing-test
  frontier: n 8, mean turns 7.12, mean tool calls 6.38, mean cost $0.176096, pass rate 8/8 (100%)
    passed, in the means: sess-e778387f1cb0, sess-4679b2b91a3e, sess-485741aec4da, sess-58bc4c439302, sess-046f6bb2c3b9, sess-dd2e683296e0, sess-037de8e19457, sess-f61f363e6a5c
    failed, pass rate only: none
  owned: n 1, mean turns 6.00, mean tool calls 5.00, mean cost $0.002938 (River list), pass rate 1/3 (33%)
    passed, in the means: sess-f805428cb504
    failed, pass rate only: sess-9b43f23d9bda, sess-78d154d1ef86
  owned, local: mean cost $0 marginal; training wall time 1171.5 s (registry.json 2026-09-27T22:33:42Z: "fix-failing-test graduated: fix-failing-test-v1, trained on 8 runs in 1171.5 s.")
  escalation reruns, in neither arm: sess-f503244eee3e, sess-bd968b5c0688
  fewer turns: yes (owned 6.00 vs frontier 7.12); lower cost: River list yes ($0.002938 vs $0.176096), local yes ($0 marginal)
```

**How to read the last line.** The owned mean is one passing session, and it's a repeat. On that same state, 07, Claude took 7 turns, 734 output tokens, $0.1727 and 18.7 s. The owned model took 6 turns, 326 output tokens, $0 marginal and 125.7 s on CPU: fewer turns and fewer output tokens, but about 7× slower. On the held-out states the owned attempt added about 4 minutes before the frontier rerun and saved nothing. **No savings ratio is claimed.** One repeat pass out of three owned sessions doesn't support one.

**Spend.** $2.90 of the $3 cap, over 108 calls to Claude:
- step 1 on state 01: $0.171 (7 calls)
- the corpus: $1.409 (57 calls)
- the two escalation reruns: $0.259 (11 calls)
- two filmed `scripts/demo.sh` attempts: $0.541 (23 calls)
- two probes of under 15 tokens each
- **$0.519 (8 calls) from another lane's session that used this router's port by mistake** (`sess-7ac196e7ba36`, not in this ledger)

**No live demo film.** The second film attempt graduated on the River checkpoint, but this checkout didn't yet have River's serving fix (646d797). So the router fell back to Claude on 07, and the spend watchdog stopped the run at $0.37 before 09. That run doesn't show the owned model serving, so it isn't published. Another attempt would have gone over the $3 cap.

The ledger, sessions, metrics and registry are in `/home/ubuntu/jelly-corpus/claude-live/` on the build host, with the corpus, checkpoint and eval logs beside it.

## Real benchmark (OpenAI frontier vs small vs River-trained owned)

**Real, 2026-09-27 22:57–23:08Z, OpenAI credit.** This section uses OpenAI models. The Claude Haiku 4.5 numbers above are a separate, earlier baseline; nothing here mixes the two.

**Arms.** Frontier: **OpenAI `gpt-5.5`**. Small: **OpenAI `gpt-5.4-mini`**. Owned: **the River-trained model** `river://9a2699b3-ce6f-4182-9da8-824a68de9c84/sampler_weights/fix-failing-test-v1` (Qwen3.5-9B LoRA, trained on the 8 Claude Haiku 4.5 sessions of broken states 01–08; [River section](#river-the-owned-model-trained-and-served-on-river-qwen35-9b)). Both OpenAI arms ran on the priority tier with `reasoning_effort: none` (`OPENAI_EXTRA_BODY`): on Chat Completions, every GPT-5.x after `gpt-5` rejects function tools beside a reasoning effort, and OpenCode sends one. We checked that with one 16-token call per model.

**`graduate bench --tasks 09,10,07 --arms frontier,small,owned`** (`bench-20260927T225656Z`, git `7c80099`). 09 and 10 were not in the owned model's training data; 07 is a repeat of a trained state. One run per task and arm. Every session is real OpenCode through the router, verified by the task's test. Means per session:

| Arm | Model | Pass | Output tokens | Input tokens | Cached | Cost | Turns | Wall p50 (s) |
|---|---|---|---|---|---|---|---|---|
| frontier | OpenAI `gpt-5.5` | 3/3 | 670 | 227,400 | 86% | $0.2808 | 8 | 23.8 |
| small | OpenAI `gpt-5.4-mini` | 3/3 | 804 | 267,915 | 87% | $0.0469 | 9 | 81.4 |
| owned | River-trained `fix-failing-test-v1` | 3/3 | 820 | 16,026 | 0% | $0.0060 | 9 | 33.8 |

Sessions: frontier `sess-65546dfe4106` (09), `sess-f5788965e0b7` (10), `sess-4c276eda1a19` (07); small `sess-f9f388eddf8c`, `sess-b99051b8a1f0`, `sess-ce2f5df24988`; owned `sess-64a4a0796956`, `sess-e5ecaf329a4b`, `sess-87ddcb52646b`. Full record: `bench/latest/results.json`.

**Read it honestly.**
- **Output tokens, the headline metric, did not go down.** The owned model used 820 a session against `gpt-5.5`'s 670 (+22%). It passed all 3, including both states it never trained on, with zero frontier calls.
- **Cost went down 47×** ($0.0060 vs $0.2808 a session), because the owned model is served a compacted prompt of ~2k tokens a call instead of OpenCode's ~28k, at the owned rate. That rate is River's Qwen3.6-35B-A3B preview price in `prices.json`, an upper bound for the 9B; River exposes no billing call, so the owned dollars are priced, not billed.
- OpenAI costs are at standard list prices (`gpt-5.5` $5 / $0.50 cached / $30 per 1M; `gpt-5.4-mini` $0.75 / $0.075 / $4.50). The priority tier bills more than that.
- 3 runs per arm is too few for a pass rate.

**Live run on the public data, big model to small model** (22:59–23:08Z, one router on the public data directory, no task-type hints, so Memorable recall classified every session, and the agents used GBrain's MCP tools to read and write shared notes):
1. `graduate swarm --agents 3` on broken states 01–05 through OpenAI `gpt-5.5`: **5 of 5 verified** (720–831 output tokens, ~$0.30 each).
2. At 5 verified runs the task type went READY. Approving it trained a **fresh** LoRA on River on those 5 sessions: Qwen3.5-9B, 15 steps, loss 0.480 → 0.034, 95.5 s, `river://d8703e97-6a1a-4248-a883-ca5bdb6d670c/sampler_weights/fix-failing-test-v1`, GRADUATED.
3. Broken states 06, 08 and 09 then **routed to that River model and passed with zero frontier calls** (1,388 / 1,562 / 1,334 output tokens, $0.007–0.011 each). None of the three was in its 5 training sessions. 07 went to `gpt-5.5` and passed there, because Memorable recall missed: its best hit (0.79, `procedures/f1390bbe-add-tests-test-mod-07-py`) is a procedure another data directory's run wrote to the shared Memorable store, and this directory's `data/slug_map.json` maps only procedures its own runs ingested, so the router named a new task type from the prompt (`the-test-is-failing-fix-the-code-so-it`) and sent it, safely, to the frontier.

Earlier the same evening, on the previous public data copy with the first River model: 7 of 7 owned sessions passed (repeats 03, 05, 06, 07, 08, held-out 09, 10), zero frontier calls.

**Memorable → GBrain migration: rolled back** (23:25Z). The plan was to move Memorable's 23 procedures from its local encrypted file into GBrain with Memorable's native integration (`memorable init gbrain` plus GBrain's `integrations.memorable` switch). `memorable init gbrain` failed with `writer_coordinator_required: source topology must be drained and changed through writer administration`, and left Memorable half-switched. A retry with no GBrain process running hit the same wall: GBrain's docs make a new writer a deliberate ownership change on the shared brain (`gbrain sources writer …` with a reviewed admin fingerprint), an operator decision we did not take at the freeze. We restored its store from the backup taken just before: backend local, read-write, 23 procedures, and a real `memorable recall` on task 09's prompt scored 0.727 (`procedures/5fc5911b-add-test-mod-09-py-test-cases`). Nothing was migrated; Memorable and GBrain run side by side.

**`make e2e` (#59), live:** `sess-406b1acb3086` on OpenAI `gpt-5.4-mini`, verify exit 0, 13 calls, $0.0571 of its $0.10 cap. Its credit probe asked for 1 output token, which GPT-5.x answers with 400; it now asks for 16.

**OpenAI spend for all of the above:** $3.68 at list prices (bench $1.10 including one aborted attempt, public-data runs $2.53, e2e $0.06), under the $25 cap.

## Offline rehearsal (stub frontier)

**Final, 2026-09-27, offline.** Measured on main `9e47e5d` (CI green), without OpenAI credit: the key answers `429 insufficient_quota` (last checked 18:01Z). So in every session below, the frontier is `scripts/stub-upstream.py`, a scripted stand-in with made-up token counts, and zero OpenAI calls were made. The owned model is real: the `fix-failing-test-v3` LoRA checkpoint (Qwen2.5-Coder-0.5B), served on this machine's CPU ([`docs/pretrained-model.md`](pretrained-model.md)).

## Headline: verification and escalation work end to end

In the final demo run, broken state 09 is new to the model (held out). The graduated task type routes it to the owned model, which reads the right file and makes an edit, and **the verify command fails it (exit 1)**. The escalator resets the repo and reruns the session on the frontier, which passes (exit 0). The failed session stays in `ledger.jsonl` and is **kept as a negative example** (`data/fix-failing-test.neg.jsonl`) for the next training round. The user gets a passing result either way.

In the same run, broken state 07, a repeat of a task the model trained on, **passes on the owned model**: exit 0, 4 calls, all served by the local checkpoint, zero frontier calls. The session ids are in [Demo run](#demo-run) below.

## Owned model savings: n/a

**n/a.** With no OpenAI credit, the owned model learned from 8 scripted stub sessions (broken states 01–08), and the frontier side of every comparison is the stub. There is no real baseline, so no savings ratio is claimed. The owned 07 numbers are real; the frontier numbers next to them are not.

**Owned model, v3, per state.** On main `9e47e5d`, which includes #109's tool-call parsing fix, so tool calls now reach OpenCode. "Repeat" means the state was in the training data; "held out" means it wasn't.

| State | Kind | Session | What the owned model did | Output tokens | Turns | Wall (s) | Verify |
|---|---|---|---|---|---|---|---|
| 07 | repeat | `sess-1c9c30abc60e` (demo), `sess-d2671375167b` (bench) | read, the right edit, "Fixed." | 84 | 4 | 45.8, 41.5 | **exit 0** both |
| 06 | repeat | `sess-1672bfeb0784` (demo), `sess-11a55ac7fc7e` (bench) | the right edit with a stray leading `"` in `oldString`, so it doesn't apply | 84 | 4 | 39.1, 39.8 | exit 1 both |
| 08 | repeat | `sess-681c94d00362` (bench) | the same stray-quote edit | 91 | 4 | 26.4 | exit 1 |
| 09 | held out | `sess-613ea4976c0f` (demo), `sess-02d7643a7aa9`, `sess-249efbb09815` | `read calc/mod_09.py`, an `edit` whose old and new text are identical | 84 | 4 | 41.5, 35.8, 35.7 | exit 1 all |
| 10 | held out | `sess-c8913db8d628` (bench) | edited `round(…, 1)` to `round(…, 2)`; the bug is the `10` that should be `100` | 99 | 4 | 32.5 | exit 1 |

Every failure escalated to a frontier rerun, and in the demo runs the rerun passed. "bench" means `graduate bench --arms owned` on the stub frontier. That's 2 of 9 owned sessions passed, both repeats. The #109 audit's eval passed 06 and 08 too; through this harness they fail on the stray quote.

## How the numbers are measured

- **Headline metric: output tokens per session, before and after.** Prompt caching discounts re-sent input; it does nothing for output tokens or turns, so those are the fair comparison.
- **Before:** the frontier model with the provider's prompt caching on. Cached tokens are counted separately and billed at the cached rate (`prices.json`, contracts §9), so the baseline is the cheapest honest frontier number, not a strawman.
- **After:** the same task type after graduation, verified by the same test command. A failed session has no "after": the Change column says n/a.
- Every number comes from `ledger.jsonl` (contracts §2): one row per session, written by `graduate run` after the verify command exits. Turns, tokens and cost are the router's per-session aggregate (#17).
- Pass rate counts verify exit codes. Forced failures (`GRADUATE_FORCE_FAIL=1`) count as failures.

## Demo run

`scripts/demo.sh` rewrites this section after every run. This one is the final offline run, `make record` (the recording is [`recordings/offline-rehearsal.mp4`](recordings/offline-rehearsal.mp4)). A live run (`scripts/live.sh`, see [SUBMISSION.md](../SUBMISSION.md#if-credit-arrives)) replaces it.

<!-- demo.sh:begin -->
### Last demo run: 2026-09-27T18:45Z

**STUB FRONTIER, NOT REAL FRONTIER NUMBERS.** The frontier was `scripts/stub-upstream.py`: zero OpenAI calls, scripted sessions and made-up token counts. Rows served by `owned` are the local checkpoint on CPU: their tokens, turns and wall time are real; their cost is priced at the `owned` rate in `prices.json`. A live run replaces this section.

Baseline: mean of the 5 verified frontier runs before graduation (the staged corpus plus broken state 05), with the provider's prompt caching on: 80% of their input tokens were cached and billed at the cached rate. Your model: its first passing session after graduation (a failed session is never counted as savings), graduated on the checkpoint fix-failing-test-v3, trained before the demo.

| | Frontier baseline, caching on | Your model, broken state 07 | Change |
|---|---|---|---|
| Output tokens | 160 | 84 | n/a: stub frontier |
| Input tokens (cached included) | 100000 | 4032 | n/a: stub frontier |
| Cached input tokens | 80000 | 0 | n/a: stub frontier |
| Cost (USD) | 0.058 | 0.001 | n/a: stub frontier |
| Turns (model calls) | 4 | 4 | n/a: stub frontier |
| Tool calls | 2 | 2 | n/a: stub frontier |
| Wall time (s) | 5.8 | 45.8 | n/a: stub frontier |

- Your model's sessions: `07` exit 0, `09` exit 1. Broken states 01-08 are the training data of the v1-v3 checkpoints (docs/pretrained-model.md), so a pass on 01-08 is a repeat of a trained task, not a held-out result; 09 and 10 are held out.
- Pass rate: frontier 5 of 5 sessions; owned 1 of 2 (forced failures included).
- Safety path: owned attempt `sess-613ea4976c0f` exit 1, a real failure of your model; frontier rerun `sess-084cc7223223` exit 0, escalated_from `sess-613ea4976c0f`. The failed row stays in `ledger.jsonl`.
- Task types in the ledger: `fix-failing-test` 8.
- All sessions (8): 0.35 USD, 1128 output tokens.
<!-- demo.sh:end -->

## Bench (#56)

The real bench table (OpenAI `gpt-5.5` vs `gpt-5.4-mini` vs the River-trained model) is in [Real benchmark](#real-benchmark-openai-frontier-vs-small-vs-river-trained-owned). In the offline rehearsal the frontier arm could only run against the stub, which measures nothing; the owned rows from then are in the per-state table above.

## River: the owned model trained and served on River (Qwen3.5-9B)

**2026-09-27, 22:17-22:29Z, live.** The same task type (`fix-failing-test`), trained with LoRA on River instead of this machine's CPU, on a base of at most 9B parameters. `get_capabilities()` listed 13 models; `Qwen/Qwen3.5-9B` is the only one at or under 9B.

**Training data:** the 8 real, verified sessions of the big model, Claude Haiku 4.5, on broken states 01-08 (exit 0 each). Broken states 09 and 10 are held out.

**Training:**

| What | Value |
|---|---|
| Base | `Qwen/Qwen3.5-9B`, LoRA rank 16, lr 2e-4, grad clip 1.0 |
| Records | 8 sessions, compacted to ~2.1-2.5k tokens each (the prompt the model is also served) |
| Steps | 24 (3 passes over the 8 sessions), one session per step |
| Loss | 0.261 (step 1) → 0.030 (step 24); per step: 0.261 0.181 0.171 0.176 0.152 0.121 0.203 0.135 0.059 0.079 0.094 0.071 0.065 0.081 0.093 0.073 0.024 0.031 0.054 0.032 0.038 0.043 0.067 0.030 |
| Time on River | 110 s of training steps (~3.5 s a step), 122 s wall-clock from start to checkpoint saved |
| Checkpoint | `river://9a2699b3-ce6f-4182-9da8-824a68de9c84/sampler_weights/fix-failing-test-v1` |
| Registry | `GRADUATED`, `model` = that river:// path, `serving` = `checkpoint` (the contract's value for a checkpoint path; the `river://` scheme picks the River backend) |

**Serving through the router** (real OpenCode, River serves every call of an owned session, a failure escalates to Claude Haiku 4.5):

| State | Kind | Session | What happened | River calls | Wall (s) | Verify |
|---|---|---|---|---|---|---|
| 07 | repeat | `sess-dea68a189eb1` | before the fix below: one `read .`, then an empty answer ended the session | 3 | 14.9 | exit 1 → escalated, Claude rerun `sess-532648dffd73` exit 0 ($0.2026) |
| 09 | held out | `sess-ab8fc7b22291` | the same empty answer after one call | 3 | 14.1 | exit 1 → escalated, Claude rerun `sess-fe2979894c63` exit 0 ($0.1451) |
| 07 | repeat | `sess-f135b8444c2f` | read the test, read `calc/mod_07.py`, the right edit (`"aeio"` → `"aeiou"`), ran the test, "Test passes." | 7 of 7 | 28.8 | **exit 0 on River alone** |
| 09 | held out | `sess-d1db6229fc80` | read the test and `calc/mod_09.py`, then the right edit (reverse the word order). The serving cap was reached there, so Claude ran the test and wrote the last message | 5 of 7 | 26.8 | exit 0, **mixed session, not counted as an owned pass** |
| 09 | held out, clean rerun | `sess-f4139463e73a` | read the test, read `calc/mod_09.py`, the right edit (reverse the word order), ran pytest, "Done. The test now passes." | 8 of 8, **0 frontier calls** | 31.0 | **exit 0 on River alone** |

The empty answers had one cause: River returns the fine-tuned model's whole answer as `reasoning_content` (Qwen3.5's template opens `<think>` and the model never closes it), with its tool calls in Qwen3.5's XML form. The backend now reads both (`graduate/registrar/train.py`, `parse` and `RiverBackend.complete`); the second pair of rows is after that fix.

**Result, honestly:** after the fix, 2 owned passes on River in 2 clean runs: repeat 07 and **held-out 09** (a state not in the training data), each with zero frontier calls. The earlier mixed 09 is not counted. 10 was not run. Two runs are too few for a pass rate.

**Spend on River:** 25 training steps (24 + a 1-step probe) and 28 serving calls (1 probe, 6 before the fix, 1 replay of the empty answer, 12 after, then 8 for the clean 09 under a separate 10-call cap). About 42 k prompt tokens and 2.0 k output tokens served in all. The River SDK exposes no billing call, so the dollar cost is not measured here; at the owned rates in `prices.json` (River's Qwen3.6-35B-A3B preview rates, an upper bound for the 9B) the served calls come to $0.015. **Claude Haiku 4.5 spend** for the two escalations and the two frontier calls in the mixed 09: $0.405.
