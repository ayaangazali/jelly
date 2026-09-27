"""GET /app serves the product frontend; its assets load through the /ui mount and every API it calls exists."""

import json
import re

from conftest import ROOT


def test_app_page_and_its_assets_are_served(router, workdir):
    page = router("GET", "/app")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert router("GET", "/app/explore/compare").text == page.text  # clean paths: the page routes itself
    assets = re.findall(r'(?:href|src)="(/ui/app/[^"]+)"', page.text)
    assert {"/ui/app/app.css", "/ui/app/app.js", "/ui/app/live.js", "/ui/app/providers.js", "/ui/app/pricing.js"} <= set(assets)
    for a in assets:
        assert router("GET", a).status_code == 200, a


def test_every_api_the_app_reads_answers_json(router, workdir):
    js = (ROOT / "ui/app/app.js").read_text(encoding="utf-8")
    for url in ["/state", "/api/swarm", "/api/sample", "/api/race"]:
        assert f'"{url}"' in js, url
        assert isinstance(router("GET", url).json(), dict), url
    assert router("GET", "/api/consent/nope").json()["error"].startswith("No task type")


def _row(sid, routed, exit_code=0, escalated_from=None, prompt="Fix test_mod_05."):
    return {"session_id": sid, "prompt": prompt, "routed_to": routed, "exit_code": exit_code, "escalated_from": escalated_from}


def test_race_pairs_each_owned_run_with_a_first_try_frontier_run_of_the_same_prompt(router, workdir):
    rows = [
        _row("sess-f1", "frontier"),
        _row("sess-o1", "owned"),
        _row("sess-o2", "owned", exit_code=1),
        _row("sess-f2", "frontier", escalated_from="sess-o2"),
        _row("sess-o3", "owned", prompt="Another task, never on the frontier."),
    ]
    (workdir / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (workdir / "sessions").mkdir()
    call = {"ts": "2026-09-27T21:20:10Z", "usage": {"output_tokens": 60}, "latency_ms": 610}
    (workdir / "sessions/sess-o1.jsonl").write_text(json.dumps(call) + "\n")

    pairs = router("GET", "/api/race").json()["pairs"]
    assert [(p["owned"]["row"]["session_id"], p["frontier"]["row"]["session_id"], p["match"]) for p in pairs] == [
        ("sess-o2", "sess-f1", "prompt"),  # newest owned first; the escalation rerun is not the first-try frontier run
        ("sess-o1", "sess-f1", "prompt"),
    ]
    assert pairs[0]["rescue"]["session_id"] == "sess-f2" and pairs[1]["rescue"] is None
    assert pairs[1]["owned"]["log"] == [call] and pairs[1]["frontier"]["log"] is None


def test_race_with_no_ledger_has_no_pairs(router, workdir):
    assert router("GET", "/api/race").json()["pairs"] == []


def test_replay_gives_each_run_its_tool_steps_and_each_task_type_its_newest_loss_curve(router, workdir):
    (workdir / "ledger.jsonl").write_text(json.dumps(_row("sess-o1", "owned")) + "\n" + json.dumps(_row("sess-x", "frontier")) + "\n")
    (workdir / "sessions").mkdir()
    edit = {"function": {"name": "edit", "arguments": json.dumps({"file_path": "calc/mod_05.py\nmore"})}}
    calls = [{"response": {"tool_calls": [edit]}}, {"response": {"content": "Fixed."}}]
    (workdir / "sessions/sess-o1.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls))
    (workdir / "data/checkpoints").mkdir(parents=True)
    (workdir / "data/checkpoints/fix-failing-test-v3.loss.jsonl").write_text('{"step": 1, "loss": 2.35, "secs": 21.2}\n')

    got = router("GET", "/api/replay").json()
    assert [r["steps"] for r in got["runs"]] == [["edit calc/mod_05.py"], []]
    assert got["loss"] == {"fix-failing-test": {"name": "fix-failing-test-v3", "steps": [{"step": 1, "loss": 2.35, "secs": 21.2}]}}


def test_provider_calls_cover_the_whole_trace_not_the_last_100(router, workdir):
    memorable = {"who": "Runner → Memorable", "call": "memorable ingest t.json", "result": "procedures/x"}
    noise = {"who": "Router → Metrics", "call": "append metrics.jsonl", "result": "ok"}
    (workdir / "trace.jsonl").write_text(json.dumps(memorable) + "\n" + "".join(json.dumps(noise) + "\n" for _ in range(150)))
    assert router("GET", "/api/provider-calls").json() == [memorable]


def test_pricing_lists_every_call_newest_first_with_the_prices(router, workdir):
    calls = [{"ts": f"2026-09-27T22:0{i}:00Z", "upstream": "frontier", "model": "gpt-5.5", "cost_usd": 0.01 * i} for i in range(3)]
    (workdir / "metrics.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls))
    got = router("GET", "/api/pricing").json()
    assert got["calls"] == calls[::-1] and set(got["prices"]) >= {"frontier", "owned"}


def test_race_falls_back_to_a_verified_run_of_the_same_task_type(router, workdir):
    rows = [
        {**_row("sess-f1", "frontier", prompt="Fix test_mod_01."), "task_type": "fix-failing-test"},
        {**_row("sess-f2", "frontier", exit_code=1, prompt="Fix test_mod_02."), "task_type": "fix-failing-test"},
        {**_row("sess-o9", "owned", prompt="Fix test_mod_09."), "task_type": "fix-failing-test"},
        {**_row("sess-o7", "owned", prompt="Something else."), "task_type": "update-changelog"},
    ]
    (workdir / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    pairs = router("GET", "/api/race").json()["pairs"]
    assert [(p["owned"]["row"]["session_id"], p["frontier"]["row"]["session_id"], p["match"]) for p in pairs] == [("sess-o9", "sess-f1", "task_type")]


def test_training_data_lists_every_record_and_rejects_odd_names(router, workdir):
    (workdir / "data").mkdir()
    recs = [{"messages": [{"role": "user", "content": f"run {i}"}], "metadata": {"session_id": f"sess-{i}"}} for i in range(3)]
    (workdir / "data/fix-failing-test.chat.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    assert router("GET", "/api/training-data/fix-failing-test").json()["runs"] == recs
    odd = router("GET", "/api/training-data/..%2Fsecrets")
    assert odd.status_code == 404 or odd.json().get("runs") == []  # never another file's records
