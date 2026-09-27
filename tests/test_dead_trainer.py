"""#116: a trainer the OS kills (no Python exception) must not leave the task type in TRAINING forever."""

import asyncio
import json
import os
import shutil
import signal
import time
from pathlib import Path

import httpx
import pytest

from conftest import ROOT
from graduate import registry, watcher
from graduate.router import consent

T = "write-migration"


class Polled(Exception):
    pass


def one_poll():
    """Run the real watch() loop for exactly one poll."""

    def stop(_):
        raise Polled

    with pytest.MonkeyPatch.context() as m, pytest.raises(Polled):
        m.setattr(watcher.time, "sleep", stop)
        watcher.watch()


def test_killed_trainer_returns_to_ready_within_one_poll(workdir, monkeypatch):
    shutil.copy(ROOT / "registry.example.json", "registry.json")
    os.mkdir("data")
    record = json.loads((ROOT / "fixtures/sft-chat.example.json").read_text())
    Path(f"data/{T}.chat.jsonl").write_text(json.dumps(record) + "\n")
    monkeypatch.setattr(
        consent, "TRAIN_CMD", ["sh", "-c", "echo $$ > trainer.pid; exec sleep 60"]
    )

    async def approve():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=consent.app), base_url="http://t"
        ) as c:
            return await c.post(f"/api/consent/{T}")

    assert asyncio.run(approve()).status_code == 202
    pidfile = Path("trainer.pid")
    while not pidfile.exists() or not pidfile.read_text().endswith("\n"):
        time.sleep(0.01)
    pid = int(pidfile.read_text())
    try:
        one_poll()
        assert (
            registry.load()["task_types"][T]["state"] == "TRAINING"
        )
    finally:
        os.kill(pid, signal.SIGKILL)
    while watcher.started(pid):
        time.sleep(0.01)

    one_poll()
    reg = registry.load()
    assert reg["task_types"][T]["state"] == "READY"
    assert "trainer" not in reg["task_types"][T]
    assert (reg["events"][0]["kind"], reg["events"][0]["text"]) == (
        "training",
        "Training stopped without finishing (exit unknown). Approve again to retry.",
    )


def test_reused_pid_counts_as_dead(workdir):
    shutil.copy(ROOT / "registry.example.json", "registry.json")
    registry.set_consent(T, True)
    registry.transition(T, "TRAINING")
    registry.update(
        T, trainer={"pid": os.getpid(), "started": watcher.started(os.getpid()) - 3600}
    )
    watcher.reap()
    assert registry.load()["task_types"][T]["state"] == "READY"
