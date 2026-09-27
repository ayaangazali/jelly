"""registry.json state machine (#18). Shape: graduate/contracts.md §1, §5.

Public surface for #19 #20 #22 #23 #24 #25:
  load()                              -> the whole registry dict (read-only snapshot)
  transition(task_type, to, **fields) -> the updated TaskType; raises IllegalTransition
  update(task_type, **fields)         -> set counters/fields without a state change
  set_consent(task_type, bool)        -> the only way to change `consent`
  add_event(kind, task_type, text)    -> newest-first event log, capped at 200

Every write is a locked read-modify-write followed by an atomic replace, so
concurrent processes never see or produce a half-written file.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

from graduate import gbrain, trace

REGISTRY_PATH = "registry.json"
LOCK_PATH = "registry.lock"
GRADUATE_N = int(os.environ.get("GRADUATE_N", "5"))
EVENT_CAP = 200
EVENT_KINDS = {
    "run",
    "ready",
    "consent",
    "training",
    "graduated",
    "failed",
    "escalated",
    "probation",
    "error",
}

# (from, to) -> (trace who, nodes, edges). Anything not listed is illegal (contracts §1).
_TRAIN = ("Consent → Registrar", ["consent", "registrar", "registry"], ["approved"])
LEGAL = {
    ("LEARNING", "READY"): (
        "Watcher → registry.json",
        ["watcher", "registry"],
        ["ready"],
    ),
    ("READY", "TRAINING"): _TRAIN,
    ("TRAINING", "GRADUATED"): (
        "Registrar → registry.json",
        ["registrar", "registry"],
        ["graduate"],
    ),
    ("TRAINING", "READY"): ("Registrar → registry.json", ["registrar", "registry"], []),
    ("GRADUATED", "PROBATION"): (
        "Escalator → Router",
        ["escalator", "registry", "router"],
        ["rerun"],
    ),
    ("PROBATION", "TRAINING"): _TRAIN,
}


class IllegalTransition(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_task_type(task_type):
    return {
        "title": task_type,
        "state": "LEARNING",
        "consent": False,
        "verify_command": "",
        "procedure_slug": None,
        "verified_runs": 0,
        "failed_runs": 0,
        "baseline": None,
        "current": None,
        "model": None,
        "serving": None,
        "deployment": None,
        "trained_on_runs": 0,
        "graduated_at": None,
        "verified_since_graduation": 0,
        "failures_since_graduation": 0,
    }


def load() -> dict:
    """Snapshot of registry.json. Safe without the lock: writers replace the file atomically."""
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"task_types": {}, "events": []}


def _write(reg):
    tmp = REGISTRY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, REGISTRY_PATH)


@contextmanager
def _locked():
    """Exclusive read-modify-write. flock is advisory: every writer must go through here."""
    with open(LOCK_PATH, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reg = load()
        yield reg
        _write(reg)


def _check_fields(fields):
    bad = {"state", "consent"} & fields.keys()
    if bad:
        raise ValueError(
            f"{sorted(bad)} change only through transition() / set_consent()"
        )


def transition(task_type: str, to_state: str, **fields) -> dict:
    """Move task_type to to_state, applying fields in the same write. Raises IllegalTransition."""
    _check_fields(fields)
    with _locked() as reg:
        tt = reg["task_types"].get(task_type)
        if tt is None:
            raise IllegalTransition(f"unknown task type {task_type!r}")
        edge = LEGAL.get((tt["state"], to_state))
        if edge is None:
            raise IllegalTransition(f"{task_type}: {tt['state']} -> {to_state}")
        # The spawned trainer's pid (#116) is valid for one TRAINING only.
        tt.pop("trainer", None)
        tt.update(fields)
        n = GRADUATE_N
        if (
            to_state == "READY"
            and tt["state"] == "LEARNING"
            and tt["verified_runs"] < n
        ):
            raise IllegalTransition(
                f"{task_type}: {tt['verified_runs']} of {n} verified runs"
            )
        if to_state == "TRAINING" and not tt["consent"]:
            raise IllegalTransition(f"{task_type}: no consent to send data to River")
        from_state, tt["state"] = tt["state"], to_state
    who, nodes, edges = edge
    trace.emit(
        who,
        f"registry.transition({task_type!r}, {to_state!r})",
        f"{from_state} → {to_state}",
        18,
        nodes,
        edges,
    )
    if to_state in ("GRADUATED", "PROBATION"):
        gbrain.publish(
            reg["task_types"],
            os.path.join(os.path.dirname(REGISTRY_PATH), "GRADUATED.md"),
        )
    return tt


def update(task_type: str, **fields) -> dict:
    """Set fields (counts, baseline, ...) without a state change. Creates the task type as LEARNING."""
    _check_fields(fields)
    with _locked() as reg:
        tt = reg["task_types"].setdefault(task_type, _new_task_type(task_type))
        tt.update(fields)
    return tt


def set_consent(task_type: str, consent: bool) -> None:
    with _locked() as reg:
        reg["task_types"].setdefault(task_type, _new_task_type(task_type))[
            "consent"
        ] = bool(consent)


def add_event(kind: str, task_type: str, text: str) -> None:
    if kind not in EVENT_KINDS:
        raise ValueError(f"unknown event kind {kind!r}")
    with _locked() as reg:
        reg["events"] = [
            {"ts": _now(), "kind": kind, "task_type": task_type, "text": text}
        ] + reg["events"][: EVENT_CAP - 1]


def _bump(path, times):
    """Concurrent-writer worker for the self-check."""
    global REGISTRY_PATH, LOCK_PATH
    REGISTRY_PATH, LOCK_PATH = path, path + ".lock"
    for _ in range(times):
        with _locked() as reg:
            reg["task_types"]["t"]["verified_runs"] += 1


def _raises(exc, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except exc:
        return
    raise AssertionError(f"{fn.__name__}{args} did not raise {exc.__name__}")


if __name__ == "__main__":
    import multiprocessing
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp()
    REGISTRY_PATH, LOCK_PATH = (
        os.path.join(tmp, "registry.json"),
        os.path.join(tmp, "registry.lock"),
    )
    trace.TRACE_PATH = os.path.join(tmp, "trace.jsonl")
    os.environ["GBRAIN_BIN"] = "false"
    GRADUATE_N = 5

    # The fixture loads, and a locked write keeps the rest of it intact.
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "..", "registry.example.json"),
        REGISTRY_PATH,
    )
    fixture = load()
    assert {tt["state"] for tt in fixture["task_types"].values()} == {
        "LEARNING",
        "READY",
        "TRAINING",
        "GRADUATED",
        "PROBATION",
    }
    update("fix-failing-test", verified_runs=5)
    fixture["task_types"]["fix-failing-test"]["verified_runs"] = 5
    assert load() == fixture
    os.remove(REGISTRY_PATH)

    # Guards and illegal moves.
    update("t", title="Test", verified_runs=4)
    assert load()["task_types"]["t"]["state"] == "LEARNING"
    _raises(IllegalTransition, transition, "nope", "READY")
    _raises(IllegalTransition, transition, "t", "GRADUATED")
    _raises(IllegalTransition, transition, "t", "READY")  # 4 < N
    transition("t", "READY", verified_runs=5)

    # No path into TRAINING without consent.
    _raises(IllegalTransition, transition, "t", "TRAINING")
    _raises(ValueError, transition, "t", "TRAINING", consent=True)
    _raises(ValueError, update, "t", consent=True)
    _raises(ValueError, update, "t", state="TRAINING")
    assert load()["task_types"]["t"]["state"] == "READY"
    set_consent("t", True)

    # Every legal transition.
    transition("t", "TRAINING")
    transition("t", "READY")
    transition("t", "TRAINING")
    transition(
        "t",
        "GRADUATED",
        model="river://run-x/sampler_weights/t-v1",
        graduated_at=_now(),
    )
    transition("t", "PROBATION")
    set_consent("t", False)
    _raises(IllegalTransition, transition, "t", "TRAINING")
    set_consent("t", True)
    tt = transition("t", "TRAINING")
    assert tt["state"] == "TRAINING" and tt["model"].endswith("t-v1")

    # trace.emit lit ready, graduate and rerun.
    with open(trace.TRACE_PATH, encoding="utf-8") as f:
        edges = {e for line in f for e in json.loads(line)["edges"]}
    assert {"ready", "graduate", "rerun", "approved"} <= edges, edges

    # Event log: newest first, capped.
    for i in range(EVENT_CAP + 50):
        add_event("run", "t", f"run {i}")
    _raises(ValueError, add_event, "bogus", "t", "x")
    events = load()["events"]
    assert len(events) == EVENT_CAP and events[0]["text"] == f"run {EVENT_CAP + 49}"

    # Concurrent writers: two processes, 100 updates each, while this process keeps reading.
    update("t", verified_runs=0)
    procs = [
        multiprocessing.Process(target=_bump, args=(REGISTRY_PATH, 100))
        for _ in range(2)
    ]
    for p in procs:
        p.start()
    reads = 0
    while any(p.is_alive() for p in procs):
        load()  # would raise JSONDecodeError on a torn file
        reads += 1
    for p in procs:
        p.join()
        assert p.exitcode == 0
    assert load()["task_types"]["t"]["verified_runs"] == 200, load()["task_types"]["t"][
        "verified_runs"
    ]

    shutil.rmtree(tmp)
    print(
        f"registry self-check ok: 6 legal transitions, consent gate, events capped, 2x100 concurrent writes ({reads} reads mid-write)"
    )
