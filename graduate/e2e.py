"""`make e2e` (#59): one live OpenCode session through the router on demo broken state 01, on the cheapest model,
under hard caps enforced here. The estimate prints before any call.

    [E2E_CAP_USD=0.10] [E2E_CAP_CALLS=20] python -m graduate.e2e       (from the repo root)

Exits 0 with `skipped: no key` when OPENAI_API_KEY is absent (environment or .env), and with `skipped: no credit`
when a probe of 1 call and at most 16 output tokens answers 429 insufficient_quota (the free GET /v1/models says 200 either way).
A watchdog reads the router's metrics.jsonl and stops the session (router and OpenCode) while the call in flight plus
one more like the priciest so far still fit under both caps; then `CAP HIT`, exit 1. OPENAI_BASE_URL points it at a
stub: scripts/corpus-dryrun.sh proves both caps offline. Everything it writes lands in backups/e2e-<time>/.
"""

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from graduate import bench, ledger
from graduate.router import upstream

CAP_USD = float(os.environ.get("E2E_CAP_USD", "0.10"))
CAP_CALLS = int(os.environ.get("E2E_CAP_CALLS", "20"))
MODEL = bench.SMALL["model"]  # the cheapest model that runs the agent loop
TASK = "01"
http = httpx.Client(timeout=30)


def probe(key):
    """One call for at most 16 output tokens (the free GET /v1/models says 200 without credit too): None when the key can spend,
    else why not. scripts/live.sh refuses on it as well."""
    r = http.post(
        upstream.URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "ok"}],
            "max_completion_tokens": 16,  # 1 answers 400 on GPT-5.x: the output limit is hit first
        },
    )
    if r.status_code == 429 and "insufficient_quota" in r.text:
        return "no credit"
    if (
        r.status_code != 200
    ):  # a rejected key, an unknown model, a rate limit: no session
        return f"FAIL: probe {r.status_code}: {r.text[:200]}"


def main():
    print(
        f"plan   1 session, demo broken state {TASK}, {MODEL} via {upstream.BASE_URL}"
    )
    print(
        f"est.   ${bench.estimate(MODEL, 'frontier'):.3f} + a 16-token credit probe  (caps ${CAP_USD:.2f}, {CAP_CALLS} calls)"
    )
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("skipped: no key")
        return 0
    if why := probe(key):
        print("skipped: no credit" if why == "no credit" else why)
        return 0 if why == "no credit" else 1

    root = bench.ROOT
    out = Path("backups") / f"e2e-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out.mkdir(parents=True)
    os.chdir(
        out
    )  # the router's metrics.jsonl and sessions/, and the runner's ledger.jsonl
    subprocess.run(
        [root / "scripts/reset-demo.sh", TASK], check=True, stdout=subprocess.DEVNULL
    )
    with open("router.log", "w") as log:
        router, url = bench.start_router(MODEL, log)
    env = {
        **os.environ,
        "GRADUATE_ROUTER": url,
        "OPENCODE_CONFIG_CONTENT": json.dumps(
            {"provider": {"graduate": {"options": {"baseURL": url + "/v1"}}}}
        ),
    }
    del env["OPENAI_API_KEY"]  # only the router holds the key
    cmd = [
        "graduate",
        "run",
        "--task-file",
        root / f"demo-repo/tasks/{TASK}.json",
        "--repo",
        root / "demo-repo",
    ]
    run = subprocess.Popen([*map(str, cmd), "--timeout", "300"], env=env)
    capped = False
    try:
        while run.poll() is None:
            costs = [bench.cost(m, m["upstream"]) for m in bench.metrics()]
            # stop while the call in flight and one more like the priciest still fit under both caps
            if not capped and (
                len(costs) + 2 > CAP_CALLS
                or sum(costs) + 2 * max(costs, default=0) > CAP_USD
            ):
                capped = True
                router.terminate()
                ps = subprocess.run(
                    ["pgrep", "-P", str(run.pid)], capture_output=True, text=True
                ).stdout
                for pid in ps.split():  # OpenCode leads its own process group
                    os.killpg(int(pid), signal.SIGKILL)
            time.sleep(0.1)
    finally:
        router.terminate()
        subprocess.run(
            [root / "scripts/reset-demo.sh", "clean"], stdout=subprocess.DEVNULL
        )
    calls = bench.metrics()
    row = (ledger.rows() or [{"session_id": "no session", "exit_code": 1}])[-1]
    print(
        f"{'CAP HIT: ' if capped else ''}e2e {row['session_id']} exit {row['exit_code']} · {len(calls)} calls · "
        f"${bench.spent():.4f} of ${CAP_USD:.2f} · {out}"
    )
    return 1 if capped else row["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
