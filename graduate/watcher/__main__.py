import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

from graduate import registry
from graduate.watcher import LEDGER_PATH, scan, verify_pattern, watch

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "ledger.example.jsonl"


def check():
    base = json.loads(FIXTURE.read_text().splitlines()[0])  # a verified frontier row
    os.chdir(tempfile.mkdtemp())

    def row(i, **kw):
        return (
            json.dumps({**base, "session_id": f"sess-{i:012x}", "turns": 10 + i, **kw})
            + "\n"
        )

    ledger = [row(i) for i in range(4)] + [
        row(10, exit_code=1),  # failed frontier: failed_runs only
        row(11, escalated_from="sess-000000000010"),  # escalation rerun: not counted
        row(12, routed_to="owned", turns=3),  # owned: verified_since_graduation only
        row(13, task_type="unknown"),  # unmatched: ignored
    ]
    Path(LEDGER_PATH).write_text("".join(ledger))
    scan()
    tt = registry.load()["task_types"]["fix-failing-test"]
    assert (tt["state"], tt["verified_runs"], tt["failed_runs"]) == (
        "LEARNING",
        4,
        1,
    ), tt
    assert tt["verified_since_graduation"] == 1 and tt["current"]["turns"] == 3, tt
    assert tt["baseline"]["turns"] == (10 + 11 + 12 + 13) / 4, tt["baseline"]
    assert tt["procedure_slug"] == base["procedure_slug"]
    assert "unknown" not in registry.load()["task_types"]
    assert (tt["title"], tt["verify_command"]) == ("Fix failing test", base["verify_command"]), tt
    assert verify_pattern(["pytest -q tests/test_mod_01.py", "pytest -q tests/test_mod_07.py"]) == "pytest -q tests/test_mod_*.py"
    assert verify_pattern(["make test", "pytest -q"]) == "make test"

    threading.Thread(target=watch, daemon=True).start()
    time.sleep(1.5)
    t0 = time.monotonic()
    with open(LEDGER_PATH, "a") as f:
        f.write(row(4))
    # scan() writes the READY state, then the ready event: wait for the event
    while not registry.load()["events"]:
        assert time.monotonic() - t0 < 2, "not READY within 2 s"
        time.sleep(0.05)
    flip = time.monotonic() - t0
    reg = registry.load()
    assert [e["kind"] for e in reg["events"]] == ["ready"], reg["events"]
    assert reg["task_types"]["fix-failing-test"]["state"] == "READY"

    scan()
    scan()
    assert registry.load() == reg, "replay is not idempotent"

    edges = [
        e["edges"] for e in map(json.loads, open("trace.jsonl")) if e["issue"] == 19
    ]
    assert ["tail"] in edges and ["tail", "ready"] in edges, edges
    print(f"watcher self-check ok: READY {flip:.2f}s after the 5th verified row")


if __name__ == "__main__":
    if sys.argv[1:] == ["--once"]:
        scan()
    elif sys.argv[1:] == ["--check"]:
        check()
    else:
        watch()
