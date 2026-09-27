# Results (#31)

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

No frontier bench table: with no credit, `graduate bench` can only run its frontier arm against the stub, and the stub's scripted sessions measure nothing. The owned arm's rows are in the per-state table above.

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

The empty answers had one cause: River returns the fine-tuned model's whole answer as `reasoning_content` (Qwen3.5's template opens `<think>` and the model never closes it), with its tool calls in Qwen3.5's XML form. The backend now reads both (`graduate/registrar/train.py`, `parse` and `RiverBackend.complete`); the second pair of rows is after that fix.

**Result, honestly:** 1 owned pass on River out of 1 clean run, on a repeat (07). On held-out 09 the River model wrote the correct fix, but the session ended mixed because the spend cap ran out, so 09 is not claimed. Nothing on 10.

**Spend on River:** 25 training steps (24 + a 1-step probe) and 20 serving calls (the cap: 1 probe, 6 before the fix, 1 replay of the empty answer, 12 after). About 23 k prompt tokens and 1.6 k output tokens served in all. The River SDK exposes no billing call, so the dollar cost is not measured here; at the owned rates in `prices.json` (River's Qwen3.6-35B-A3B preview rates, an upper bound for the 9B) the served calls come to $0.0084. **Claude Haiku 4.5 spend** for the two escalations and the two frontier calls in the mixed 09: $0.405.
