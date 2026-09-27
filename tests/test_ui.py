"""The dashboard's sidecar assets (#55): what the projector would show as unstyled or blank if a path broke."""

import re

from conftest import ROOT


def test_router_serves_every_local_ui_asset(router):
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "projector.css").read_text(encoding="utf-8")
    paths = re.findall(r'(?:href|src)="(/ui/[^"]+)"', html) + ["/ui/" + u for u in re.findall(r'url\("([^"]+)"\)', css)]
    assert {"/ui/projector.css", "/ui/present.js", "/ui/fonts/archivo.woff2"} <= set(paths)
    assert router("GET", "/").status_code == 200
    for path in paths:
        assert router("GET", path).status_code == 200, path


def test_results_freezes_the_dashboard_state(workdir, capsys):
    import json
    import os

    from graduate import cli

    os.chdir(cli._demo_dir())
    cli.main(["results", "--out", str(workdir / "results/state.json")])
    got = json.loads((workdir / "results/state.json").read_text(encoding="utf-8"))
    want = json.loads((ROOT / "fixtures/state.example.json").read_text(encoding="utf-8"))
    assert list(got) == list(want)
    for key in ("registry", "ledger", "trace", "terminal", "session_log"):
        assert got[key] == want[key], key
    assert "?state=/" in capsys.readouterr().out


def test_state_is_served_when_consent_is_imported_first(workdir):
    import os
    import subprocess
    import sys

    code = ("import graduate.router.consent\nfrom fastapi.testclient import TestClient\nimport graduate.router.app as a\n"
            "assert TestClient(a.app).get('/state').status_code == 200")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert r.returncode == 0, r.stderr[-800:]


def test_compare_before_any_bench_is_not_a_server_error(router, workdir):
    r = router("GET", "/bench/latest/results.json")
    assert r.status_code == 200 and "bench/latest" in r.json()["error"]


def test_router_serves_the_latest_bench_for_compare(router, workdir):
    run = workdir / "bench" / "bench-1"
    run.mkdir(parents=True)
    (run / "results.json").write_text((ROOT / "fixtures/bench.example.json").read_text())
    (workdir / "bench" / "latest").symlink_to("bench-1")  # how graduate bench points at its newest run
    r = router("GET", "/bench/latest/results.json")
    assert r.status_code == 200 and r.json()["arms"]["owned"]["output_tokens"] == 540


def test_demo_router_says_its_numbers_are_sample_data(router, monkeypatch):
    assert router("GET", "/api/sample").json() == {"sample": False}
    monkeypatch.setenv("GRADUATE_SAMPLE", "1")  # what `graduate up --demo` sets
    assert router("GET", "/api/sample").json() == {"sample": True}
