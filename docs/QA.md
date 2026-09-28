# Manual QA: try the whole app (#64)

For a human, twice on demo day (early morning, then again at 3 PM). About 25 minutes. It costs $0: every model call goes to the stub upstream (`scripts/stub-upstream.py`). Part E is the one exception: it needs OpenAI credit.

When a step does not match, write down the step number, what you expected and what you got, and open an issue. Then carry on: the steps after it usually still work.

**You need:** a clone of the repo, Python 3.11+, `jq`, `curl`, [OpenCode](https://opencode.ai) (`curl -fsSL https://opencode.ai/install | bash`) and a browser. Port 4141 must be free: stop any `graduate up` or `make dev` that is still running.

## A. Install and automated checks (5 min)

1. `python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[test]'`
   **Expected:** the install ends with `Successfully installed … graduate-0.1.0 …`.
2. `graduate`
   **Expected:** a usage line, then `run`, `init`, `up` and `bench`, one line of help each.
3. `make test`
   **Expected:** `N passed` and no failures, in about 30 s.
4. `make e2e-replay`
   **Expected:** in 1 to 2 minutes, real OpenCode sessions scroll by, each ending in `exit 0 · 1/1 passed`. The run ends with `dry run ok: backups/dryrun-<time>`. It uses ports 4241 and 4299, never 4141.

## B. The dashboard with no key (3 min)

5. `graduate up --demo`
   **Expected:** `dashboard: http://localhost:4141/   (Ctrl-C stops)`.
6. Open http://localhost:4141/ (Overview).
   **Expected:** the header says "Connected to localhost:4141". "$0.42 saved across 2 runs your own models handled". A banner: "Write a migration has 5 verified runs and can graduate". Six task types in six different states. The Activity list is newest first. The browser console shows no errors.
7. Click **Showcase**.
   **Expected:** "Fix a failing test", output tokens **25,800 → 540**, "48× less", then Cost, Turns, Wall time and Tests pass rows, a Graduation card "4 of 5 passing frontier runs" and a Safety net card.
8. Click **Compare**, then **Under the hood**, then **Setup**.
   **Expected:** Compare says "No bench results yet: /bench/latest/results.json answered 404. Run `graduate bench`…" (the demo has no bench). The other two views render with no blank panel. The browser console shows no errors.
9. Press Ctrl-C in the terminal.
   **Expected:** `stopped`.

## C. The full loop on the stub (12 min)

Keep three terminals open in the repo root, each with `. .venv/bin/activate`. If `ledger.jsonl`, `registry.json`, `sessions/` or `data/` are left over from an earlier try, move them into `backups/` first.

10. Terminal 1: `python3 scripts/stub-upstream.py 4199 /tmp/auth.log`
    **Expected:** no output. It keeps running.
11. Terminal 2: `OPENAI_BASE_URL=http://127.0.0.1:4199/v1 OPENAI_API_KEY=sk-stub graduate up`
    **Expected:** `dashboard: http://localhost:4141/`. Open it: the task table is empty, and "$0.000 saved".
12. Terminal 3: five runs.
    ```bash
    for n in 01 02 03 04 05; do scripts/reset-demo.sh $n; graduate run --task-file demo-repo/tasks/$n.json --repo demo-repo; done
    ```
    **Expected:** OpenCode reads a file, edits it and says "Fixed.". Each run ends with `sess-… frontier exit 0 · 1/1 passed · 4 turns · $0.05792 · <10s`. After each run the dashboard adds the run within about a second.
13. Dashboard.
    **Expected:** a banner says "fix-failing-test has 5 verified runs and can graduate". The row says "Ready to train" with 5 filled bars. Activity says "…has 5 verified runs. Waiting for you to approve the training data."
14. Click **Review training data**.
    **Expected:** the page opens with "Send 5 runs to River to train "fix-failing-test"?". Under "One record, exactly as it would be sent" it says `No training data built for fix-failing-test yet. Run: python -m graduate.registrar.dataset fix-failing-test`, and **Approve and train** is greyed out. Run that command in terminal 3.
    **Expected:** `fix-failing-test: 5 records, … tokens … → data/`. Reload the page: it now shows the token total and one full record, and the button is enabled.
15. Click **Approve and train**.
    **Expected:** a toast "Approved. Training started." and the page returns to Overview. The row now says "Training". Activity shows the consent and "Training started on River with 5 runs.".
16. Stand in for training. The owned trainer (#22) is not on main yet. In terminal 3:
    ```bash
    python -c "from graduate import registry; registry.transition('fix-failing-test', 'GRADUATED', model='river://qa-drill/fix-failing-test')"
    ```
    **Expected:** no output. The row says "Graduated" and "Goes to: Your model".
17. Escalation drill:
    ```bash
    scripts/reset-demo.sh 06 && GRADUATE_FORCE_FAIL=1 graduate run --task-file demo-repo/tasks/06.json --repo demo-repo
    ```
    **Expected:** two sessions. The first is `sess-A owned exit 1`, then `sess-B frontier exit 0 · 1/1 passed`, then `sess-A owned_then_frontier → sess-B exit 0`. Activity (newest first) shows "fix-failing-test: your model's attempt was marked failed for the demo (GRADUATE_FORCE_FAIL=1), failure 1 of 3…" and then "…reran the task on the frontier as sess-B: tests pass." The state stays "Graduated". Only the third failure moves it to probation.
18. `scripts/reset-demo.sh clean && git status demo-repo`
    **Expected:** `nothing to commit, working tree clean`.

## D. The benchmark, dry run (2 min)

19. Terminal 3: `graduate bench --dry-run`
    **Expected:** two lines. They name the tasks, each arm and its model (owned is `river://qa-drill/…` after step 16), and the estimate against the cap. The dollar amounts vary; for example:
    ```
    plan  tasks 01,07 · arms frontier(gpt-5.6-terra) small(gpt-5.4-mini) owned(river://qa-drill/fix-failing-test)
    est.  frontier 2 x $0.06 + small 2 x $0.06 + owned 2 x $0.02 = $0.28  (cap $1.00, spent today $0.41 of $25.00)
    ```
    "Spent today" counts every call in this directory's `metrics.jsonl`. Here those are stub calls priced as if they were real. Nothing is written, and `bench/` does not appear.
20. `graduate bench --max-usd 0.10`
    **Expected:** it refuses before running anything: `refused: the estimate crosses the cap…`.
21. Optional ($0, about 1 minute): `graduate bench --yes`, with terminals 1 and 2 still running.
    **Expected:** in about a minute, a table with one row per arm (frontier, small, owned), output tokens first, then `spent $… of $1.00 · bench/<stamp>/results.json`. On the stub, every arm shows 160 output tokens and 2/2 passing. Small costs less per run than frontier ($0.0217 against $0.0579): it is priced at gpt-5.4-mini's rates. The owned arm shows `river://qa-drill/…`, but the frontier serves its calls until #37 lands. Open http://localhost:4141/#/compare: the same numbers, one column per arm, output tokens as the first row and tests pass as the last.

Stop terminals 1 and 2 with Ctrl-C. Move the state aside: `mkdir -p backups/qa && mv ledger.jsonl metrics.jsonl sessions registry.json data trace.jsonl terminal.log bench backups/qa/`.

## E. With OpenAI credit only (5 min, at most $0.10)

Skip this part while the key returns `429 insufficient_quota`.

22. `graduate init`
    **Expected:** `python … ok`, `opencode …`, `key ok: GET https://api.openai.com/v1/models -> 200`, then `.env written (mode 600)`, prices.json, registry.json and the opencode.json provider. The models check is free, so "key ok" does not prove the key has credit.
23. `graduate up`. Then, in a second terminal: `scripts/reset-demo.sh 01 && graduate run --task-file demo-repo/tasks/01.json --repo demo-repo`
    **Expected:** `sess-… frontier exit 0 · 1/1 passed`, with a cost of a few cents. The dashboard shows the run with real token counts. With no credit you get OpenCode's 429 error and `exit 1`.

## Known gaps (already filed; do not re-file)

- #75: with no key, a model call returns `502 … Illegal header value b'Bearer '` instead of a one-line fix.
- #76: task types the watcher creates show the slug as the title, and the consent screen says "checked with ." (empty verify command).
- #77: the Overview verify commands overflow their rows at 1280x720.
- Owned serving (#37) and training (#22) are not on main yet. That is why step 16 stands in for training and the "owned" run in step 17 is served by the frontier.
