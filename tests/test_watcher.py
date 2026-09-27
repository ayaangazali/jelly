"""The watcher survives a torn ledger (#132): a bad line is skipped, a failing scan never kills the thread."""

import json
import shutil

import pytest

from conftest import ROOT, assert_trace, example
from graduate import registry, watcher


def test_a_truncated_and_a_non_json_line_do_not_stop_ready(workdir):
    base = example("fixtures/ledger.example.jsonl")  # a verified frontier row
    rows = [
        json.dumps({**base, "session_id": f"sess-{i:012x}"})
        for i in range(registry.GRADUATE_N)
    ]
    rows.insert(
        2, rows[0][:40]
    )  # a runner killed mid-append, the next row on its own line
    rows.insert(4, "not json")
    (workdir / "ledger.jsonl").write_text("\n".join(rows) + "\n")

    watcher.scan()

    tt = registry.load()["task_types"]["fix-failing-test"]
    assert (tt["state"], tt["verified_runs"]) == ("READY", registry.GRADUATE_N)
    [tail] = [e for e in assert_trace() if e["edges"] == ["tail"]]
    assert (
        tail["result"]
        == f"{registry.GRADUATE_N} rows, 1 task types, 2 unreadable lines skipped"
    )


def test_watch_survives_a_scan_that_raises(workdir, monkeypatch):
    shutil.copy(ROOT / "fixtures/ledger.example.jsonl", "ledger.jsonl")
    monkeypatch.setattr(registry, "GRADUATE_N", 1)
    real, calls = watcher.scan, []

    def scan():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("registry.json: disk full")
        return real()

    ticks = iter(range(3))
    monkeypatch.setattr(watcher, "scan", scan)
    monkeypatch.setattr(
        watcher, "_mtime", lambda: next(ticks)
    )  # the ledger changes every poll

    def sleep(_):
        if len(calls) == 2:
            raise StopIteration  # two polls done: leave the loop

    monkeypatch.setattr(watcher.time, "sleep", sleep)

    with pytest.raises(StopIteration):
        watcher.watch()

    assert registry.load()["task_types"]["fix-failing-test"]["state"] == "READY"
    [err] = [e for e in assert_trace() if e["result"].startswith("scan failed")]
    assert "disk full" in err["result"]
