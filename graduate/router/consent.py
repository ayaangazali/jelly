import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from graduate import registry
from graduate.registrar.train import RiverBackend, backend
from graduate.watcher import started
from graduate.router.app import app

APPROVABLE = ("READY", "PROBATION")
TRAIN_CMD = [sys.executable, "-m", "graduate.registrar.train"]
router = APIRouter()


def _where():
    try:
        chosen = backend()
    except RuntimeError:
        return {"backend": "none", "where": "nowhere", "destination": "nowhere: GRADUATE_OWNED_BACKEND=none, so the frontier serves everything"}
    if isinstance(chosen, RiverBackend):
        return {"backend": "river", "where": "River", "destination": "your River account"}
    return {"backend": "local", "where": "this machine", "destination": "this machine: a local model, so the records never leave it"}


def _task(task_type):
    return registry.load()["task_types"].get(task_type)


def _records(task_type):
    path = Path("data") / f"{task_type}.chat.jsonl"
    if not path.exists():
        return None
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _tokens(task_type):
    path = Path("data") / f"{task_type}.tok.jsonl"
    if not path.exists():
        return None
    return sum(len(json.loads(l)["input_ids"]) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


def _error(status, message):
    return JSONResponse({"error": message}, status)


@router.get("/api/consent/{task_type}")
def review(task_type: str):
    tt = _task(task_type)
    if tt is None:
        return _error(404, f"No task type called {task_type!r}.")
    records = _records(task_type)
    if not records:
        return {
            "task_type": task_type,
            "state": tt["state"],
            "consent": tt["consent"],
            "records": 0,
            "tokens": None,
            **_where(),
            "sample": None,
            "error": f"No training data built for {task_type} yet. Run: python -m graduate.registrar.dataset {task_type}",
        }
    return {
        "task_type": task_type,
        "state": tt["state"],
        "consent": tt["consent"],
        "records": len(records),
        "tokens": _tokens(task_type),
        **_where(),
        "sample": records[0],
    }


@router.post("/api/consent/{task_type}")
def approve(task_type: str):
    tt = _task(task_type)
    if tt is None:
        return _error(404, f"No task type called {task_type!r}.")
    if tt["state"] not in APPROVABLE:
        return _error(409, f"{task_type} is {tt['state']}. Approval applies to READY or PROBATION.")
    records = _records(task_type)
    if not records:
        return _error(409, f"Nothing to approve: no training data built for {task_type} yet.")
    registry.set_consent(task_type, True)
    where = _where()["where"]
    registry.add_event("consent", task_type, f"You approved training {task_type} on {where} with {len(records)} runs.")
    registry.transition(task_type, "TRAINING")
    log = Path("data") / f"{task_type}.train.log"
    with log.open("ab") as out:
        p = subprocess.Popen([*TRAIN_CMD, task_type], stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    registry.update(task_type, trainer={"pid": p.pid, "started": started(p.pid)})  # the watcher spots a silent death (#116)
    registry.add_event("training", task_type, f"Training started on {where} with {len(records)} runs.")
    return JSONResponse({"task_type": task_type, "state": "TRAINING", "records": len(records), "log": str(log)}, 202)


@router.delete("/api/consent/{task_type}")
def revoke(task_type: str):
    tt = _task(task_type)
    if tt is None:
        return _error(404, f"No task type called {task_type!r}.")
    if tt["state"] not in APPROVABLE:
        return _error(409, f"{task_type} is {tt['state']}. Consent can only be revoked before training starts.")
    registry.set_consent(task_type, False)
    registry.add_event("consent", task_type, f"You revoked consent for {task_type}. Nothing will be trained.")
    return {"task_type": task_type, "consent": False}


app.include_router(router)


if __name__ == "__main__":
    import asyncio
    import os
    import shutil
    import tempfile

    import httpx

    from graduate import trace

    root = Path(__file__).resolve().parents[2]
    os.chdir(tempfile.mkdtemp())
    trace.TRACE_PATH = os.devnull
    shutil.copy(root / "registry.example.json", "registry.json")
    Path("data").mkdir()
    sample = json.loads((root / "fixtures" / "sft-chat.example.json").read_text())
    Path("data/write-migration.chat.jsonl").write_text((json.dumps(sample) + "\n") * 5)
    Path("data/write-migration.tok.jsonl").write_text((root / "fixtures" / "sft-wire.example.json").read_text().strip() + "\n")
    os.environ.pop("RIVER_API_KEY", None)
    os.environ.pop("GRADUATE_OWNED_BACKEND", None)
    sys.modules["graduate.router.consent"].TRAIN_CMD[:] = [sys.executable, "-c", "import sys; open('trained.txt', 'w').write(sys.argv[1])"]

    async def main():
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
        r = await c.get("/api/consent/write-migration")
        body = r.json()
        assert r.status_code == 200 and body["records"] == 5 and body["tokens"] == 17 and body["sample"] == sample, body
        assert (body["backend"], body["where"]) == ("local", "this machine"), body
        os.environ["RIVER_API_KEY"] = "rv_test"
        assert (await c.get("/api/consent/write-migration")).json()["backend"] == "river"
        del os.environ["RIVER_API_KEY"]
        assert (await c.get("/api/consent/../../etc/passwd")).status_code == 404
        assert (await c.get("/api/consent/nope")).status_code == 404
        r = await c.get("/api/consent/fix-failing-test")
        assert r.status_code == 200 and r.json()["sample"] is None and "registrar.dataset" in r.json()["error"]
        assert (await c.post("/api/consent/update-changelog")).status_code == 409
        r = await c.delete("/api/consent/write-migration")
        assert r.status_code == 200 and registry.load()["task_types"]["write-migration"]["consent"] is False
        r = await c.post("/api/consent/write-migration")
        assert r.status_code == 202 and r.json()["state"] == "TRAINING", r.text
        tt = registry.load()["task_types"]["write-migration"]
        assert tt["state"] == "TRAINING" and tt["consent"] is True
        assert [e["kind"] for e in registry.load()["events"][:2]] == ["training", "consent"]
        assert "River" not in registry.load()["events"][0]["text"], registry.load()["events"][0]
        assert (await c.delete("/api/consent/write-migration")).status_code == 409
        assert (await c.post("/api/consent/write-migration")).status_code == 409
        for _ in range(50):
            if Path("trained.txt").exists():
                break
            await asyncio.sleep(0.1)
        assert Path("trained.txt").read_text() == "write-migration"

    asyncio.run(main())
    print("consent self-check ok")
