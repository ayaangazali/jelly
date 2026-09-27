# Corpus (#6)

Broken states 01–08 of `demo-repo`, each run once through the router (#13) and the runner (#34) with frontier routing. The session logs are the SFT data for #21 and the #7 pre-train. Four verified rows stay in the live ledger, so `fix-failing-test` sits at 4 of 5 and graduates on stage with the fifth run.

## Model and prices

Frontier model: **`gpt-4.1-mini`**. Per million tokens, OpenAI standard tier, checked 2026-09-27:

| Input | Cached input | Output |
|---|---|---|
| 0.40 | 0.10 | 1.60 |

Why not the cheaper `gpt-5-mini` (0.25 / 0.025 / 2.00): OpenCode 1.18.32 sends `max_tokens: 32000` on every call (captured against a local stub, zero OpenAI calls). GPT-5-family models expect `max_completion_tokens` instead [INFERENCE: from OpenAI's docs, not tried live], so `gpt-5-mini` would need a field rewrite in the router. `gpt-4.1-mini` accepts the request unchanged and is a reliable tool caller. Each tool-bearing call carries about 25k prompt tokens (10 tool schemas plus the system prompt), and after the first call most of that is cached.

`prices.json` in the repo root (untracked, contracts §9) carries these under `frontier`. The router reads it at start, so every `cost_usd` in `metrics.jsonl` and the ledger uses them.

## Run it

From the repo root, with `prices.json` in place and no earlier `ledger.jsonl`, `metrics.jsonl`, `sessions/` or `registry.json` (move them aside):

```bash
. .venv/bin/activate
(set -a; . ~/super.env; set +a; exec uvicorn graduate.router.app:app --port 4141) &   # the key lives only in the router's env
scripts/corpus.sh
```

[`scripts/corpus.sh`](../scripts/corpus.sh) does the whole issue:

1. Prints a cost estimate. It uses the per-call cost and calls per session measured in `metrics.jsonl` if frontier rows exist, otherwise 12 calls of 25k prompt tokens (80% cached) and 400 output tokens at `prices.json` rates.
2. Runs `graduate run` on broken states 01–08, one at a time.
3. Enforces the caps: **400 upstream calls** and **USD 6** (`CAP_CALLS`, `CAP_USD`). They count only rows it adds to the router's `metrics.jsonl`. It checks before each state, and a once-a-second watchdog kills OpenCode's process group mid-session once a cap is hit, so the count can overshoot by the calls that finish within that second (the instant stub fit 2 extra; a real model call takes seconds). The killed session still gets its ledger row, as a failure.
4. Relabels `task_type: "unknown"` rows to `fix-failing-test`. The classifier (#20) is not on main, and every corpus session is the demo task by construction.
5. Stages the ledger. The live `ledger.jsonl` keeps the first 4 verified rows plus every failed one (negative examples). The other verified rows go to `backups/stage-ledger.jsonl`. Every session log stays in `sessions/` for #7.
6. Rebuilds `registry.json` with `python -m graduate.watcher --once`: `fix-failing-test` at 4 of 5.
7. Prints the baseline averages, including the cached-token share.
8. Tars `ledger.jsonl`, `sessions/`, `registry.json`, `metrics.jsonl`, `prices.json` and `backups/stage-ledger.jsonl` into `backups/corpus-<time>.tgz`.
9. Copies the tarball and the uncompressed files to `/home/ubuntu/jelly-corpus/` (`CORPUS_DIR`). Worktrees are disposable; the #21 dataset lane and the #7 pre-train read this copy.

Order matters in step 5: the watcher flips a task type to READY at 5 verified runs and never flips it back. Don't start the watcher, or anything that runs one, against the unsplit ledger.

## Dry run (offline)

```bash
. .venv/bin/activate && scripts/corpus-dryrun.sh
```

This makes zero OpenAI calls. [`scripts/stub-upstream.py`](../scripts/stub-upstream.py) plays the model: it streams a `read`, then an `edit` that undoes the planted bug, then "Fixed.", with cached-token usage. The dry run then:

1. Starts the stub and a router pointed at it.
2. Runs `corpus.sh` under a 6-call cap and checks that the corpus stops early.
3. Runs the full 8 states.
4. Checks the 4 + 4 ledger split, `registry.json` at 4 of 5, one session log per row containing the edit round trip, a cached share over 0, and that the upstream only ever saw the server key.
5. Restores the tarball into a clean dir and rebuilds the registry there.

Its output goes to `backups/dryrun-<time>/`.

## Restore

From the repo root of any checkout:

```bash
tar xzf /home/ubuntu/jelly-corpus/corpus-<time>.tgz   # ledger.jsonl, sessions/, registry.json, metrics.jsonl, prices.json, backups/stage-ledger.jsonl
rm registry.json && python -m graduate.watcher --once   # optional: rebuild the registry from the ledger, 4 of 5
```

Or copy the uncompressed files from `/home/ubuntu/jelly-corpus/` into the repo root. To use all 8 verified runs, for example to graduate without a live fifth run, append `backups/stage-ledger.jsonl` to `ledger.jsonl`.

## Results

Pending. The OpenAI project behind `OPENAI_API_KEY` has no credits (`insufficient_quota`), so no real session has run yet. The offline dry run passes.
