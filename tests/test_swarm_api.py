"""GET /api/swarm feeds the dashboard's #/swarm view: swarm/latest.json plus the last 50 A2A trace events."""

import json

from conftest import ROOT, assert_shape, example

FIXTURE = json.loads((ROOT / "fixtures/swarm.example.json").read_text(encoding="utf-8"))


def test_before_any_swarm_the_view_gets_the_command_to_run(router, workdir):
    got = router("GET", "/api/swarm").json()
    assert "graduate swarm" in got["error"] and got["agents"] == [] and got["a2a"] == []


def test_serves_the_latest_run_and_only_the_last_50_a2a_events(router, workdir):
    run = {k: v for k, v in FIXTURE.items() if k != "a2a"}
    (workdir / "swarm").mkdir()
    (workdir / "swarm/latest.json").write_text(json.dumps(run))
    read, write, other = (
        FIXTURE["a2a"][0],
        FIXTURE["a2a"][2],
        example("fixtures/trace.example.jsonl"),
    )
    events = [{**(write if i % 2 else read), "result": str(i)} for i in range(60)]
    (workdir / "trace.jsonl").write_text(
        "".join(json.dumps(e) + "\n" + json.dumps(other) + "\n" for e in events)
    )

    got = router("GET", "/api/swarm").json()
    assert_shape(got, FIXTURE)
    assert {k: got[k] for k in run} == run
    assert got["a2a"] == events[-50:]

    (workdir / "swarm/latest.json").write_text(
        '{"swarm_id": "half-writ'
    )  # the launcher mid-rewrite
    assert router("GET", "/api/swarm").json()["agents"] == run["agents"]
