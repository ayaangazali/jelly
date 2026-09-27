"""GET /app serves the product frontend; its assets load through the /ui mount and every API it calls exists."""

import json
import re

from conftest import ROOT


def test_app_page_and_its_assets_are_served(router, workdir):
    page = router("GET", "/app")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert router("GET", "/app/explore/compare").text == page.text  # clean paths: the page routes itself
    assets = re.findall(r'(?:href|src)="(/ui/app/[^"]+)"', page.text)
    assert sorted(assets) == ["/ui/app/app.css", "/ui/app/app.js", "/ui/app/live.js"]
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
    assert [(p["owned"]["row"]["session_id"], p["frontier"]["row"]["session_id"]) for p in pairs] == [
        ("sess-o2", "sess-f1"),  # newest owned first; the escalation rerun is not the first-try frontier run
        ("sess-o1", "sess-f1"),
    ]
    assert pairs[0]["rescue"]["session_id"] == "sess-f2" and pairs[1]["rescue"] is None
    assert pairs[1]["owned"]["log"] == [call] and pairs[1]["frontier"]["log"] is None


def test_race_with_no_ledger_has_no_pairs(router, workdir):
    assert router("GET", "/api/race").json()["pairs"] == []
