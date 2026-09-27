import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from graduate import registry, trace
from graduate.router.app import app

UI = Path(__file__).resolve().parents[2] / "ui" / "index.html"
FAIL_LIMIT = int(os.environ.get("GRADUATE_FAIL_LIMIT", "3"))
router = APIRouter()
_tails = {}


def tail(path, n):
    p = Path(path)
    try:
        st = p.stat()
    except FileNotFoundError:
        return []
    key = (str(p), n)
    hit = _tails.get(key)
    if hit and hit[0] == (st.st_size, st.st_mtime_ns):
        return hit[1]
    with p.open(encoding="utf-8", errors="replace") as f:
        lines = list(deque((l.rstrip("\n") for l in f if l.strip()), maxlen=n))
    _tails[key] = ((st.st_size, st.st_mtime_ns), lines)
    return lines


def jsonl(path, n):
    rows = []
    for line in tail(path, n):
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def totals(task_types, ledger):
    saved, owned = 0.0, 0
    for row in ledger:
        if row.get("routed_to") != "owned":
            continue
        owned += 1
        base = (task_types.get(row.get("task_type")) or {}).get("baseline") or {}
        if row.get("exit_code") == 0 and base.get("cost_usd") is not None:
            saved += base["cost_usd"] - row.get("cost_usd", 0)
    unclassified = sum(1 for r in ledger if r.get("task_type") in (None, "", "unknown"))
    return {"saved_usd": round(saved, 4), "owned_runs": owned, "unclassified_runs": unclassified}


def latest_session_log(n=4):
    logs = sorted(Path("sessions").glob("sess-*.jsonl"), key=lambda p: p.stat().st_mtime) if Path("sessions").is_dir() else []
    if not logs:
        return []
    out = []
    for row in jsonl(logs[-1], n):
        req = row.get("request") or {}
        row["request"] = {"messages": f"{len(req.get('messages') or [])} messages", "tools": f"{len(req.get('tools') or [])} tools"}
        out.append(row)
    return out


def build_state():
    reg = registry.load()
    ledger = jsonl("ledger.jsonl", 10_000)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": {"n": registry.GRADUATE_N, "fail_limit": FAIL_LIMIT},
        "registry": reg,
        "totals": totals(reg.get("task_types", {}), ledger),
        "ledger": ledger[-50:],
        "trace": jsonl(trace.TRACE_PATH, 100),
        "terminal": tail(trace.TERMINAL_PATH, 200),
        "session_log": latest_session_log(),
    }


@router.get("/state")
def state():
    return build_state()


@router.get("/", response_model=None)
def dashboard():
    if UI.exists():
        return FileResponse(UI, media_type="text/html")
    return PlainTextResponse("ui/index.html isn't on this branch yet (#15). /state is live.", 404)


app.include_router(router)
app.mount("/ui", StaticFiles(directory=UI.parent), name="ui")  # ui/projector.css, present.js, fonts/ (#55)
app.mount("/bench", StaticFiles(directory="bench", check_dir=False), name="bench")  # bench/latest/results.json for #/compare (#61)


if __name__ == "__main__":
    import asyncio
    import shutil
    import tempfile

    import httpx

    root = Path(__file__).resolve().parents[2]
    work = Path(tempfile.mkdtemp())
    os.chdir(work)
    shutil.copy(root / "registry.example.json", "registry.json")
    shutil.copy(root / "fixtures" / "ledger.example.jsonl", "ledger.jsonl")
    shutil.copy(root / "fixtures" / "trace.example.jsonl", "trace.jsonl")
    Path("sessions").mkdir()
    shutil.copy(root / "fixtures" / "session.example.jsonl", "sessions/sess-8b30c11e2d7a.jsonl")
    Path("terminal.log").write_text("$ graduate run\n1 passed in 0.04s · exit 0\n")

    async def main():
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
        s = (await c.get("/state")).json()
        assert set(s) == {"generated_at", "config", "registry", "totals", "ledger", "trace", "terminal", "session_log"}, set(s)
        assert s["registry"]["task_types"]["update-changelog"]["state"] == "GRADUATED"
        assert s["config"] == {"n": registry.GRADUATE_N, "fail_limit": FAIL_LIMIT}
        assert len(s["ledger"]) == 4 and len(s["trace"]) == 5 and s["terminal"][-1].endswith("exit 0")
        assert s["totals"] == {"saved_usd": 0.4174, "owned_runs": 2, "unclassified_runs": 0}, s["totals"]
        assert s["session_log"][-1]["request"] == {"messages": "8 messages", "tools": "3 tools"}
        with open("ledger.jsonl", "a") as f:
            f.write("not json\n" + json.dumps({"session_id": "sess-x", "task_type": "unknown", "routed_to": "frontier", "exit_code": 0}) + "\n")
        s = (await c.get("/state")).json()
        assert len(s["ledger"]) == 5 and s["totals"]["unclassified_runs"] == 1
        os.remove("registry.json")
        s = (await c.get("/state")).json()
        assert s["registry"] == {"task_types": {}, "events": []} and s["totals"]["saved_usd"] == 0
        r = await c.get("/")
        assert r.status_code in (200, 404)

    asyncio.run(main())
    print("state self-check ok")
