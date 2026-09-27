"""`graduate bench` (#56): the same demo tasks through each arm, compared on output tokens first.

    graduate bench [--tasks 01,07 | --sample N] [--repeat 1] [--arms frontier,small,owned] [--max-usd 1.00]
                   [--dry-run] [--yes] [--md] [--timeout 600]

Arms: frontier (prices.json's frontier model, caching on), small (SMALL below, or prices.json "small"), owned (the
registry's GRADUATED model; n/a until one exists). Per arm the bench starts its own router on a free port with
OPENAI_MODEL=<arm model>, runs each task through `graduate.runner.run` (reset-demo, OpenCode, verify, ledger row),
then aggregates that arm's ledger rows plus metrics.jsonl latency.

Budget: prints the plan and estimate first, refuses when the estimate crosses --max-usd or today's DAILY_CAP_USD,
checks before every run, and a watchdog kills OpenCode mid-run once spend reaches the cap. Spend is metrics.jsonl
(every model call the bench's routers served), priced per model with contracts §9.

Writes bench/<stamp>/results.json (shape: fixtures/bench.example.json; token counts, cost, turns and tool calls are
per-run means) and points bench/latest at it; --md appends the table to docs/results.md.
"""

import argparse
import json
import os
import random
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from graduate import ledger, runner
from graduate.router.upstream import _prices

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "demo-repo/tasks"
PRICES = json.loads(_prices.read_text())
# gpt-5.4-mini list price per 1M tokens (OpenRouter, checked 2026-09-27); prices.json "small" overrides it.
SMALL = PRICES.get(
    "small",
    {"model": "gpt-5.4-mini", "input": 0.75, "cached_input": 0.075, "output": 4.5},
)
DAILY_CAP_USD = 25.0  # the plan's whole-day OpenAI cap (roadmap Q2)
METRICS = Path("metrics.jsonl")
FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "cost_usd",
    "turns",
    "tool_calls",
)


def price(model, upstream):
    return (
        PRICES["owned"]
        if upstream == "owned"
        else SMALL
        if model == SMALL["model"]
        else PRICES["frontier"]
    )


def cost(rec, upstream):
    """Contracts §9 at the model's own prices: the router prices every frontier-side call as the frontier."""
    p = price(rec["model"], upstream)
    fresh = rec["input_tokens"] - rec["cached_input_tokens"]
    usd = (
        fresh * p["input"]
        + rec["cached_input_tokens"] * p["cached_input"]
        + rec["output_tokens"] * p["output"]
    )
    return usd / 1e6


def metrics():
    return (
        [json.loads(l) for l in METRICS.read_text().splitlines() if l.strip()]
        if METRICS.exists()
        else []
    )


def spent(since=0, day=None):
    return sum(
        cost(m, m["upstream"])
        for m in metrics()[since:]
        if day is None or m["ts"].startswith(day)
    )


def owned_model():
    try:
        tts = json.loads(
            Path(os.environ.get("GRADUATE_REGISTRY", "registry.json")).read_text()
        )["task_types"]
    except FileNotFoundError:
        return None
    return next(
        (
            t["model"]
            for t in tts.values()
            if t["state"] == "GRADUATED" and t.get("model")
        ),
        None,
    )


def estimate(model, upstream):
    """Per run: the mean of this model's past ledger rows, else 120k input (70% cached) and 6k output."""
    past = [
        cost(r, upstream)
        for r in ledger.rows()
        if r["model"] == model and r["routed_to"] == upstream
    ]
    prior = {
        "model": model,
        "input_tokens": 120_000,
        "cached_input_tokens": 84_000,
        "output_tokens": 6_000,
    }
    return statistics.mean(past) if past else cost(prior, upstream)


def start_router(model, log):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "graduate.router.app:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env={**os.environ, "OPENAI_MODEL": model},
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(url + "/healthz").status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit(f"router for {model} did not start; see {log.name}")


def watchdog(stop, cap, since, spare):
    """At the cap, kill every process group this process leads a child of (OpenCode), except the router's."""
    while not stop.wait(1):
        if spent(since) < cap:
            continue
        ps = subprocess.run(
            ["pgrep", "-P", str(os.getpid())], capture_output=True, text=True
        ).stdout.split()
        for pid in map(int, ps):
            try:
                if (
                    pid != spare and os.getpgid(pid) == pid
                ):  # a session leader: OpenCode, never the verify shell
                    os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return


def summarize(model, rows, note=None):
    if not rows:
        return {"model": model, "note": note, "runs": 0, "passed": 0} | dict.fromkeys(
            FIELDS + ("wall_secs_p50", "latency_ms_p50")
        )
    ids = {r["session_id"] for r in rows}
    lat = [m["latency_ms"] for m in metrics() if m["session_id"] in ids]
    rows = [r | {"cost_usd": cost(r, r["routed_to"])} for r in rows]
    means = {
        k: round(statistics.mean(r[k] for r in rows), 6 if k == "cost_usd" else None)
        for k in FIELDS
    }
    return {
        "model": model,
        "note": note,
        "runs": len(rows),
        "passed": sum(r["exit_code"] == 0 for r in rows),
        **means,
        "wall_secs_p50": statistics.median(r["wall_secs"] for r in rows),
        "latency_ms_p50": statistics.median(lat) if lat else None,
    }


def table(arms):
    head = [
        "arm",
        "model",
        "out_tok",
        "in_tok",
        "cached",
        "cost",
        "turns",
        "wall_s",
        "pass",
    ]
    body = [
        [
            name,
            a["model"] or a["note"],
            *(
                ["n/a"] * 6
                if not a["runs"]
                else [
                    f"{a['output_tokens']:,}",
                    f"{a['input_tokens']:,}",
                    f"{a['cached_input_tokens'] / max(a['input_tokens'], 1):.0%}",
                    f"${a['cost_usd']:.4f}",
                    str(a["turns"]),
                    f"{a['wall_secs_p50']:g}",
                ]
            ),
            f"{a['passed']}/{a['runs']}",
        ]
        for name, a in arms.items()
    ]
    return head, body


def main():
    p = argparse.ArgumentParser(
        prog="graduate bench", description=__doc__.split("\n")[0]
    )
    p.add_argument(
        "--tasks", default="01,07", help="demo-repo task ids, comma separated"
    )
    p.add_argument("--sample", type=int, help="N random tasks instead of --tasks")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--arms", default="frontier,small,owned")
    p.add_argument(
        "--max-usd", type=float, default=1.00, help="hard cap on this bench's spend"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="print the plan and estimate, spend $0"
    )
    p.add_argument("--yes", action="store_true", help="no confirmation prompt")
    p.add_argument(
        "--md", action="store_true", help="append the table to docs/results.md"
    )
    p.add_argument(
        "--timeout", type=float, default=600, help="per-task agent timeout, seconds"
    )
    a = p.parse_args()

    all_tasks = sorted(f.stem for f in TASKS.glob("*.json"))
    tasks = (
        sorted(random.sample(all_tasks, a.sample)) if a.sample else a.tasks.split(",")
    )
    if unknown := set(tasks) - set(all_tasks):
        raise SystemExit(f"unknown tasks {sorted(unknown)}; have {','.join(all_tasks)}")
    owned = owned_model()
    models = {
        "frontier": PRICES["frontier"]["model"],
        "small": SMALL["model"],
        "owned": owned,
    }
    arms = a.arms.split(",")
    if bad := set(arms) - set(models):
        raise SystemExit(f"unknown arms {sorted(bad)}; have {','.join(models)}")
    skipped = (
        {"owned": "n/a: nothing GRADUATED"} if "owned" in arms and not owned else {}
    )
    runnable = [arm for arm in arms if arm not in skipped]
    n = len(tasks) * a.repeat
    per_run = {
        arm: estimate(models[arm], "owned" if arm == "owned" else "frontier")
        for arm in runnable
    }
    est = n * sum(per_run.values())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    spent_today = spent(day=today)
    print(
        "plan  tasks "
        + ",".join(tasks)
        + (f" x {a.repeat}" if a.repeat > 1 else "")
        + " · arms "
        + " ".join(f"{arm}({skipped.get(arm) or models[arm]})" for arm in arms)
    )
    print(
        "est.  "
        + (
            " + ".join(f"{arm} {n} x ${per_run[arm]:.2f}" for arm in runnable)
            or "nothing to run"
        )
        + f" = ${est:.2f}  (cap ${a.max_usd:.2f}, spent today ${spent_today:.2f} of ${DAILY_CAP_USD:.2f})"
    )
    if a.dry_run or not runnable:
        return
    if est > a.max_usd or spent_today + est > DAILY_CAP_USD:
        raise SystemExit(
            "refused: the estimate crosses the cap; raise --max-usd or run fewer tasks/arms"
        )
    if not Path(runner.OPENCODE).exists():
        raise SystemExit(
            f"OpenCode not found at {runner.OPENCODE}: curl -fsSL https://opencode.ai/install | bash"
        )
    if not a.yes:
        try:
            ok = input("Proceed? [y/N] ").strip().lower() == "y"
        except EOFError:
            ok = False
        if not ok:
            raise SystemExit("not run")

    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    out = Path("bench") / stamp
    out.mkdir(parents=True)
    os.environ.pop("GRADUATE_FORCE_FAIL", None)  # a bench measures real failures only
    since, results, sessions, capped = len(metrics()), {}, [], None
    for arm in runnable:
        rows = []
        with open(out / f"router-{arm}.log", "w") as log:
            router, url = start_router(
                models["frontier"] if arm == "owned" else models[arm], log
            )
        runner.ROUTER = url
        os.environ["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            {"provider": {"graduate": {"options": {"baseURL": url + "/v1"}}}}
        )
        stop = threading.Event()
        threading.Thread(
            target=watchdog, args=(stop, a.max_usd, since, router.pid), daemon=True
        ).start()
        try:
            for task in tasks * a.repeat:
                if spent(since) + per_run[arm] > a.max_usd:
                    capped = f"CAP: stopped before {arm} {task}"
                    break
                spec = json.loads((TASKS / f"{task}.json").read_text())
                subprocess.run(
                    [ROOT / "scripts/reset-demo.sh", task],
                    check=True,
                    capture_output=True,
                )
                before = len(ledger.rows())
                runner.run(
                    spec["prompt"],
                    spec["verify"],
                    str(ROOT / "demo-repo"),
                    force_frontier=arm != "owned",
                    timeout=a.timeout,
                )
                row = ledger.rows()[
                    before
                ]  # the arm's own session; an owned failure's escalation rerun follows it
                rows.append(row)
                sessions.append(
                    {
                        "arm": arm,
                        "task": task,
                        "session_id": row["session_id"],
                        "exit_code": row["exit_code"],
                    }
                )
        finally:
            stop.set()
            router.terminate()
            router.wait()
        results[arm] = summarize(models[arm], rows, capped)
        if capped:
            break
    subprocess.run([ROOT / "scripts/reset-demo.sh", "clean"], check=True)
    results |= {arm: summarize(None, [], note) for arm, note in skipped.items()}

    total = round(spent(since), 6)
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    doc = {
        "bench_id": f"bench-{stamp}",
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": sha,
        "tasks": tasks,
        "budget": {
            "cap_usd": a.max_usd,
            "estimate_usd": round(est, 6),
            "spent_usd": total,
        },
        "arms": results,
        "sessions": sessions,
    }
    (out / "results.json").write_text(json.dumps(doc, indent=2) + "\n")
    latest = Path("bench/latest")
    latest.unlink(missing_ok=True)
    latest.symlink_to(stamp)

    head, body = table(results)
    widths = [max(len(r[i]) for r in [head, *body]) for i in range(len(head))]
    for r in [head, *body]:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    print(
        f"{capped + '; ' if capped else ''}spent ${total:.4f} of ${a.max_usd:.2f} · {out}/results.json"
    )
    if a.md:
        md = [
            f"\n## Bench {stamp} (git {sha}, tasks {','.join(tasks)})\n",
            "| " + " | ".join(head) + " |",
            "|" + "---|" * len(head),
            *("| " + " | ".join(r) + " |" for r in body),
        ]
        with open(ROOT / "docs/results.md", "a") as f:
            f.write("\n".join(md) + "\n")
    if capped:
        raise SystemExit(1)
