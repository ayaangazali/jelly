"""`graduate` dispatcher, `graduate init` file writing, `up --demo` fixture state (#57). Offline: GET /models is faked."""

import json
import os
import re
import stat
import subprocess
import sys

import httpx
import pytest

from conftest import ROOT
from graduate import cli

seen = []


def record():
    seen.append(sys.argv[:])


def test_dispatch_strips_the_command_name(monkeypatch, capsys):
    monkeypatch.setitem(cli.COMMANDS, "echo", ("test_cli:record", "test only"))
    cli.main(["echo", "--flag", "x"])
    assert seen[-1] == ["graduate echo", "--flag", "x"]
    for argv, code in (([], 2), (["nope"], 2), (["--help"], 0)):
        with pytest.raises(SystemExit) as e:
            cli.main(argv)
        assert e.value.code == code
    assert re.search(r"^  echo +test only$", capsys.readouterr().err, re.M)


@pytest.fixture
def models(workdir, monkeypatch):
    """GET /models answers `status`; every call is recorded. No network."""
    calls, status = [], [200]

    def get(url, headers, timeout):
        calls.append((url, headers["Authorization"]))
        return httpx.Response(status[0])

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("RIVER_API_KEY", raising=False)
    return calls, status


def init(*flags):
    cli.main(["init", "--no-input", *flags])


def test_init_writes_env_600_and_config(models, workdir):
    calls, _ = models
    init("--backend", "none")
    assert calls == [("https://api.openai.com/v1/models", "Bearer sk-dummy")]
    env = workdir / ".env"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert env.read_text() == "OPENAI_API_KEY=sk-dummy\nGRADUATE_OWNED_BACKEND=none\n"
    assert (workdir / "prices.json").read_text() == (
        ROOT / "fixtures/prices.example.json"
    ).read_text()
    assert json.loads((workdir / "registry.json").read_text()) == {
        "task_types": {},
        "events": [],
    }
    demo = json.loads((ROOT / "demo-repo/opencode.json").read_text())
    assert json.loads((workdir / "opencode.json").read_text()) == demo


def test_init_is_idempotent_and_keeps_what_it_does_not_own(
    models, workdir, monkeypatch
):
    calls, _ = models
    (workdir / ".env").write_text("RIVER_API_KEY=rv_x\nOPENAI_API_KEY=sk-old\n")
    (workdir / ".env").chmod(0o644)
    (workdir / "opencode.json").write_text(
        '{"provider": {"other": {}}, "theme": "dark"}'
    )
    (workdir / "registry.json").write_text('{"task_types": {"t": {}}, "events": []}')
    monkeypatch.delenv("OPENAI_API_KEY")
    init()  # the key comes from .env; RIVER_API_KEY picks river
    init()
    assert [c[1] for c in calls] == ["Bearer sk-old"] * 2
    assert (workdir / ".env").read_text() == (
        "RIVER_API_KEY=rv_x\nOPENAI_API_KEY=sk-old\nGRADUATE_OWNED_BACKEND=river\n"
    )
    assert stat.S_IMODE((workdir / ".env").stat().st_mode) == 0o600
    cfg = json.loads((workdir / "opencode.json").read_text())
    assert cfg["theme"] == "dark" and set(cfg["provider"]) == {"other", "graduate"}
    assert cfg["model"] == "graduate/graduate"
    assert "t" in json.loads((workdir / "registry.json").read_text())["task_types"]


def test_init_refuses_a_bad_or_missing_key(models, workdir, monkeypatch):
    _, status = models
    status[0] = 401
    with pytest.raises(SystemExit, match="HTTP 401"):
        init()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(SystemExit, match="up --demo"):
        init()
    assert os.listdir(workdir) == []  # nothing written on failure


def test_init_gitignores_env_in_a_repo(models, workdir):
    subprocess.run(["git", "init", "-q"], check=True)
    init()
    assert (workdir / ".gitignore").read_text() == ".env\n"
    init()
    assert (workdir / ".gitignore").read_text() == ".env\n"


def test_demo_dir_serves_the_fixture_state(workdir):
    from graduate.router.state import build_state

    os.chdir(cli._demo_dir())
    state, fixture = (
        build_state(),
        json.loads((ROOT / "fixtures/state.example.json").read_text()),
    )
    for key in ("registry", "ledger", "trace", "terminal", "session_log"):
        assert state[key] == fixture[key], key


def test_the_wheel_ships_every_dashboard_file():
    """#82: package-data globs like setuptools does (`*` stops at `/`), so ui/fonts/ needs its own pattern."""
    import tomllib

    pats = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"]["package-data"]["ui"]
    shipped = {f for pat in pats for f in (ROOT / "ui").glob(pat) if f.is_file()}
    assert {f for f in (ROOT / "ui").rglob("*") if f.is_file()} <= shipped
