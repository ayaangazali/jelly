# Results (#31)

The numbers the pitch uses. `scripts/demo.sh` rewrites the section between the `demo.sh` markers after every run; `graduate bench` (#56) appends its table under [Bench](#bench-56).

## How they are measured

- **Headline: output tokens per session, before and after.** Prompt caching discounts re-sent input; it does nothing for output tokens or turns, so those are the fair comparison.
- **Before:** the frontier model with the provider's prompt caching on. Cached tokens are counted separately and billed at the cached rate (`prices.json`, contracts §9), so the baseline is the cheapest honest frontier number, not a strawman.
- **After:** the same task type after graduation, verified by the same test command.
- Every number comes from `ledger.jsonl` (contracts §2): one row per session, written by `graduate run` after the verify command exits. Turns, tokens and cost are the router's per-session aggregate (#17).
- Pass rate counts verify exit codes. Forced failures (`GRADUATE_FORCE_FAIL=1`) count as failures.

## Demo run

<!-- demo.sh:begin -->
### Last demo run: 2026-09-27T09:41Z

**STUB RUN, NOT REAL NUMBERS.** The frontier was `scripts/stub-upstream.py`: zero OpenAI calls, scripted three-turn sessions and made-up token counts. A live run replaces this section.

Baseline: mean of the 5 verified frontier runs before graduation (the staged corpus plus broken state 05), with the provider's prompt caching on: 80% of their input tokens were cached and billed at the cached rate. After: broken state 09 on the graduated task type, graduated on the checkpoint stub://no-checkpoint-yet, trained before the demo.

| | Frontier baseline, caching on | Graduated, broken state 09 | Change |
|---|---|---|---|
| Output tokens | 160 | 160 | 0% |
| Input tokens (cached included) | 100000 | 100000 | 0% |
| Cached input tokens | 80000 | 80000 | 0% |
| Cost (USD) | 0.058 | 0.058 | 0% |
| Turns (model calls) | 4 | 4 | 0% |
| Tool calls | 2 | 2 | 0% |
| Wall time (s) | 9.34 | 9.8 | 5% |

- 09 served by: `frontier` (`gpt-5.6-terra`), exit 0. Owned serving (#37) is not on main yet, so the router fell back to the frontier and the After column is a frontier run.
- Pass rate: frontier 6 of 6 sessions; owned 0 of 1 (forced failures included).
- Safety path, broken state 10 with `GRADUATE_FORCE_FAIL=1`: owned attempt `sess-87f6ee10e011` exit 1 (forced_failure true); frontier rerun `sess-ee41ec591cf8` exit 0, escalated_from `sess-87f6ee10e011`. The failed row stays in `ledger.jsonl`; forced failures are not kept as training negatives.
- Task types in the ledger: `fix-failing-test` 8.
- All sessions (8): 0.463 USD, 1280 output tokens.
<!-- demo.sh:end -->

## Bench (#56)

<!-- graduate bench appends its table below -->
