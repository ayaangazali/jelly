import json
import os
import shutil
import subprocess
import sys

from conftest import ROOT
from graduate.router.state import build_state


def test_stdio_tools_match_state(workdir):
    shutil.copy(ROOT / "registry.example.json", "registry.json")
    shutil.copy(ROOT / "fixtures" / "ledger.example.jsonl", "ledger.jsonl")
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "graduate.status", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "graduate.savings", "arguments": {}}},
    ]
    out = subprocess.run(
        [sys.executable, "-m", "graduate.mcp"],
        input="".join(json.dumps(m) + "\n" for m in msgs),
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    ).stdout
    res = {r["id"]: r["result"] for r in map(json.loads, out.splitlines())}
    assert sorted(res) == [1, 2, 3, 4]
    assert [t["name"] for t in res[2]["tools"]] == ["graduate.status", "graduate.savings"]
    status, savings = (json.loads(res[i]["content"][0]["text"]) for i in (3, 4))
    s = build_state()
    assert status["config"] == s["config"]
    fields = ("state", "verified_runs", "failed_runs", "verified_since_graduation", "failures_since_graduation")
    assert status["task_types"] == {k: {f: t[f] for f in fields} for k, t in s["registry"]["task_types"].items()}
    assert status["task_types"]["update-changelog"]["state"] == "GRADUATED"
    assert savings == s["totals"] == {"saved_usd": 0.4174, "owned_runs": 2, "unclassified_runs": 0}


def test_bad_lines_get_errors_and_the_server_keeps_serving(workdir):
    lines = [
        "garbage",
        "[]",
        "1",
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}}),
        json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/list"}),
    ]
    out = subprocess.run(
        [sys.executable, "-m", "graduate.mcp"],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    ).stdout
    res = [json.loads(l) for l in out.splitlines()]
    codes = [(r["id"], r.get("error", {}).get("code")) for r in res]
    assert codes == [(None, -32700), (None, -32600), (None, -32600), (3, -32603), (4, None)]
    assert len(res[-1]["result"]["tools"]) == 2
