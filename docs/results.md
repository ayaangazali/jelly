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

**STUB FRONTIER, NOT REAL FRONTIER NUMBERS.** The frontier was `scripts/stub-upstream.py`: zero OpenAI calls, scripted sessions and made-up token counts. Rows served by `owned` are real: the local checkpoint on CPU. A live run replaces this section.

Baseline: mean of the 5 verified frontier runs before graduation (the staged corpus plus broken state 05), with the provider's prompt caching on: 80% of their input tokens were cached and billed at the cached rate. Your model: its first passing session after graduation (a failed session is never counted as savings), graduated on the checkpoint /home/ubuntu/jelly-corpus/checkpoints/fix-failing-test-v3, trained before the demo.

| | Frontier baseline, caching on | Your model, broken state 07 | Change |
|---|---|---|---|
| Output tokens | 160 | 84 | n/a: stub frontier |
| Input tokens (cached included) | 100000 | 4032 | n/a: stub frontier |
| Cached input tokens | 80000 | 0 | n/a: stub frontier |
| Cost (USD) | 0.058 | 0.001 | n/a: stub frontier |
| Turns (model calls) | 4 | 4 | n/a: stub frontier |
| Tool calls | 2 | 2 | n/a: stub frontier |
| Wall time (s) | 5.8 | 45.8 | n/a: stub frontier |

- Your model's sessions: `07` exit 0, `09` exit 1. Broken states 01-08 are the training data of the checkpoints in `/home/ubuntu/jelly-corpus/checkpoints/`, so a pass on 01-08 is a repeat of a trained task, not a held-out result; 09 and 10 are held out.
- Pass rate: frontier 5 of 5 sessions; owned 1 of 2 (forced failures included).
- Safety path: owned attempt `sess-613ea4976c0f` exit 1, a real failure of your model; frontier rerun `sess-084cc7223223` exit 0, escalated_from `sess-613ea4976c0f`. The failed row stays in `ledger.jsonl`.
- Task types in the ledger: `fix-failing-test` 8.
- All sessions (8): 0.35 USD, 1128 output tokens.
<!-- demo.sh:end -->

## Bench (#56)

No frontier bench table: with no credit, `graduate bench` can only run its frontier arm against the stub, and the stub's scripted sessions measure nothing. The owned arm's rows are in the per-state table above.
