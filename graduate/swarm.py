"""`graduate swarm`: many agents through GRADUATE at once (#8), the launcher of the outer system.

    graduate swarm --tasks 01,02,03 --agents N [--offline] [--launcher local|superset] [--timeout SECS]

One agent per task, round-robin when agents > tasks; at most N run at a time. All agents reuse this interpreter and its venv. Each agent gets its OWN copy of demo-repo
in a temp dir (git-initialised, broken state planted as scripts/reset-demo.sh does), then calls graduate.runner.run
through the router, so every session has its own session id and ledger row. The checkout's demo-repo is never touched.
The run record swarm/<swarm_id>.json (and its copy swarm/latest.json) in the working directory is rewritten as agents
progress. --offline serves the frontier from scripts/stub-upstream.py behind a router on free ports, as
scripts/demo.sh --offline does: zero OpenAI calls.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from graduate import runner, trace

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo-repo"
ISSUE = 8
_lock = threading.Lock()


def _bugs():
    """Broken state NN -> (old, new), read from scripts/reset-demo.sh like scripts/stub-upstream.py does."""
    text = (ROOT / "scripts/reset-demo.sh").read_text()
    return {n: (old, new) for n, old, new in re.findall(r"(\d\d)\) old='(.*)' new='(.*)' ;;", text)}


def copy(task, dest):
    """demo-repo is not its own repo, so a copy with its own git: the runner and escalator reset to its HEAD."""
    shutil.copytree(DEMO, dest, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"))
    git = ["git", "-C", str(dest), "-c", "user.name=graduate swarm", "-c", "user.email=swarm@graduate.local"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "demo-repo"]):
        subprocess.run(git + args, check=True, capture_output=True)
    old, new = _bugs()[task]
    mod = dest / f"calc/mod_{task}.py"
    mod.write_text(mod.read_text().replace(old, new))
    return dest


def save(record):
    with _lock:
        Path("swarm").mkdir(exist_ok=True)
        text = json.dumps(record, indent=2) + "\n"
        for name in (record["swarm_id"], "latest"):
            tmp = Path(f"swarm/{name}.json.tmp")
            tmp.write_text(text)
            tmp.replace(f"swarm/{name}.json")  # readers never see half a file


def _agent(a, record, work, timeout):
    task = json.loads((DEMO / f"tasks/{a['task']}.json").read_text())
    repo = copy(a["task"], work / a["agent"])
    a.update(status="running", session_id="sess-" + uuid.uuid4().hex[:12])
    save(record)
    trace.emit(
        "Swarm → Runner",
        f"graduate run --task-file demo-repo/tasks/{a['task']}.json",
        f"{a['agent']} in its own copy {repo}",
        ISSUE,
        ["swarm", "runner"],
        ["fanout"],
        a["session_id"],
    )
    try:
        row = runner.run(task["prompt"], task["verify"], str(repo), timeout=timeout, task_type=task.get("task_type"), session_id=a["session_id"])
    except Exception as e:  # one agent's crash fails that agent, never the swarm
        print(f"{a['agent']}: {e!r}", file=sys.stderr)
        row = {"exit_code": 1, "turns": 0}
    ids = {a["session_id"], row.get("session_id")}  # an escalation reruns under a new id
    edges = [edge for e in trace.recent() if e["session_id"] in ids for edge in e["edges"]]
    a.update(
        status="passed" if row["exit_code"] == 0 else "failed",
        exit_code=row["exit_code"],
        turns=row["turns"],
        a2a_read="a2a-read" in edges,
        a2a_write="a2a-write" in edges,
    )
    save(record)
    print(f"{a['agent']} task {a['task']} {a['session_id']} {a['status']} exit {a['exit_code']} · {a['turns']} turns · "
          f"{row.get('started_at', '?')} → {row.get('ended_at', '?')}", flush=True)


def swarm(tasks, agents, timeout=600, launcher="local"):
    now = datetime.now(timezone.utc)
    record = {
        "swarm_id": f"swarm-{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:4]}",
        "started": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "launcher": launcher,
        "agents": [
            {"agent": f"a{i + 1}", "task": t, "task_type": json.loads((DEMO / f"tasks/{t}.json").read_text()).get("task_type"),
             "session_id": None, "status": "queued", "exit_code": None, "turns": None, "a2a_read": False, "a2a_write": False}
            for i, t in enumerate(tasks[i % len(tasks)] for i in range(max(agents, len(tasks))))
        ],
    }
    save(record)
    print(f"{record['swarm_id']}: {len(record['agents'])} agents, {agents} at a time -> swarm/{record['swarm_id']}.json", flush=True)
    with tempfile.TemporaryDirectory(prefix=f"graduate-{record['swarm_id']}-") as work, ThreadPoolExecutor(agents) as pool:
        for f in [pool.submit(_agent, a, record, Path(work), timeout) for a in record["agents"]]:
            f.result()
    return record


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def offline(log_dir):
    """The stub frontier and a router in this directory, on free ports (scripts/demo.sh --offline, minus the demo)."""
    stub, port = _port(), _port()
    env = {**os.environ, "OPENAI_BASE_URL": f"http://127.0.0.1:{stub}/v1", "OPENAI_API_KEY": "sk-stub"}
    procs = [
        subprocess.Popen([sys.executable, str(ROOT / "scripts/stub-upstream.py"), str(stub), str(log_dir / "upstream-auth.log")]),
        subprocess.Popen(["uvicorn", "graduate.router.app:app", "--port", str(port)], env=env,
                         stdout=open(log_dir / "router.log", "w"), stderr=subprocess.STDOUT),
    ]
    for _ in range(100):
        try:
            httpx.get(f"http://localhost:{port}/healthz", timeout=1).raise_for_status()
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        sys.exit(f"router did not start: {log_dir / 'router.log'}")
    runner.ROUTER = os.environ["GRADUATE_ROUTER"] = f"http://localhost:{port}"
    os.environ["OPENCODE_CONFIG_CONTENT"] = json.dumps({"provider": {"graduate": {"options": {"baseURL": f"http://localhost:{port}/v1"}}}})
    print(f"offline: stub frontier :{stub} (zero OpenAI calls), router :{port}, logs {log_dir}", flush=True)
    return procs


def main():
    p = argparse.ArgumentParser(prog="graduate swarm")
    p.add_argument("--tasks", required=True, help="broken states, e.g. 01,02,03")
    p.add_argument("--agents", type=int, default=4, help="agents running at once (at most 8 without --force)")
    p.add_argument("--force", action="store_true", help="allow more than 8 agents at once")
    p.add_argument("--offline", action="store_true", help="stub frontier + own router: zero OpenAI calls")
    p.add_argument("--launcher", choices=["local", "superset"], default="local")
    p.add_argument("--timeout", type=float, default=600, help="per agent, seconds")
    a = p.parse_args()
    tasks = a.tasks.split(",")
    if bad := [t for t in tasks if not (DEMO / f"tasks/{t}.json").is_file()]:
        sys.exit(f"no demo-repo task {', '.join(bad)}: pick from 01-10")
    if not 1 <= a.agents <= 8 and not (a.force and a.agents > 8):
        sys.exit("--agents runs 1-8 at once (8 cores, memory shared with other runs); more needs --force")
    if a.launcher == "superset":
        # ponytail: local threads only; a Superset launch needs #8's human setup (install, sign-in, project id) first.
        why = "is not installed here" if not shutil.which("superset") else "launch is not wired yet"
        sys.exit(f"--launcher superset: the Superset CLI {why}. Use --launcher local (the default).")
    procs = []
    if a.offline:
        log_dir = Path(tempfile.mkdtemp(prefix="graduate-swarm-logs-"))
        procs = offline(log_dir)
    elif runner._router("GET", "/state") is None:
        sys.exit(f"no router at {runner.ROUTER}: start `graduate up` first, or use --offline")
    try:
        record = swarm(tasks, a.agents, a.timeout, a.launcher)
    finally:
        for proc in procs:
            proc.terminate()
    passed = sum(x["status"] == "passed" for x in record["agents"])
    print(f"{record['swarm_id']}: {passed} of {len(record['agents'])} passed")
    raise SystemExit(0 if passed == len(record["agents"]) else 1)
