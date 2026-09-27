"""`graduate` dispatcher, `graduate init` file writing, `up --demo` fixture state (#57). Offline: GET /models is faked."""

import json
import os
import re
import shutil
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
    with pytest.raises(SystemExit, match="HTTP 401; get a key at .*up --demo"):
        init()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(SystemExit, match="up --demo"):
        init()
    assert os.listdir(workdir) == []  # nothing written on failure


def test_init_strips_a_pasted_line_break_and_never_echoes_a_malformed_key(models, workdir, monkeypatch):
    """#97: httpx quotes a bad Authorization header, key and all, in its error; `init` would print it."""
    calls, _ = models
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy\r")  # sourced from a CRLF env file
    init("--backend", "none")
    assert calls == [("https://api.openai.com/v1/models", "Bearer sk-dummy")]
    assert (workdir / ".env").read_text().startswith("OPENAI_API_KEY=sk-dummy\n")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-QWZX\nPLMK")
    with pytest.raises(SystemExit) as e:
        init()
    assert "QWZX" not in str(e.value.code) and len(calls) == 1


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


def test_up_refuses_a_taken_port_before_printing_a_url(capsys):
    """#84: not the other process's dashboard URL, then uvicorn's Errno 98."""
    import socket

    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", 4141))
            s.listen()
        except OSError:
            pass  # something already listens there: the same case
        with pytest.raises(SystemExit, match="port 4141 is taken"):
            cli.main(["up", "--demo"])
    assert "dashboard" not in capsys.readouterr().out


def test_the_wheel_ships_every_dashboard_file():
    """#82: package-data globs like setuptools does (`*` stops at `/`), so ui/fonts/ needs its own pattern."""
    import tomllib

    pats = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"]["package-data"]["ui"]
    shipped = {f for pat in pats for f in (ROOT / "ui").glob(pat) if f.is_file()}
    assert {f for f in (ROOT / "ui").rglob("*") if f.is_file()} <= shipped


@pytest.mark.parametrize(
    "env, said, warns",
    [
        ({}, "owned backend: local (no RIVER_API_KEY): Approve trains on this machine", False),
        ({"RIVER_API_KEY": "rk"}, "owned backend: river (RIVER_API_KEY is set): Approve trains on River", True),
        ({"RIVER_API_KEY": "rk", "GRADUATE_OWNED_BACKEND": "local"}, "owned backend: local (GRADUATE_OWNED_BACKEND=local)", False),
        ({"GRADUATE_OWNED_BACKEND": "none"}, "owned backend: none", False),
    ],
)
def test_up_names_the_owned_backend_and_warns_on_the_river_trap(workdir, monkeypatch, capsys, env, said, warns):
    """#25: an unfunded River key on the demo laptop would make Approve fail with insufficient_funds."""
    import types

    monkeypatch.setenv("GRADUATE_SAMPLE", "")  # recorded, so the 1 that up --demo sets is undone after the test
    for k in ("RIVER_API_KEY", "GRADUATE_OWNED_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    free = types.SimpleNamespace(connect_ex=lambda addr: 111)  # :4141 is free, whatever else runs on this host
    monkeypatch.setattr(cli, "socket", types.SimpleNamespace(socket=lambda: free))
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: None)
    cli.main(["up", "--demo"])
    out, err = capsys.readouterr()
    assert said in out and out.index("owned backend") < out.index("dashboard:")
    assert ("WARNING: RIVER_API_KEY is set" in err) == warns


@pytest.mark.parametrize(
    "env, said, warns",
    [
        ({}, "owned backend: local", False),
        ({"RIVER_API_KEY": "rk"}, "owned backend: local", True),
        ({"RIVER_API_KEY": "rk", "GRADUATE_OWNED_BACKEND": "river"}, "owned backend: river", False),
    ],
)
def test_demo_sh_trains_locally_unless_told_and_warns_on_the_river_trap(tmp_path, env, said, warns):
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/demo.sh", tmp_path / "scripts")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/curl").write_text("#!/bin/sh\n")  # every port looks taken: demo.sh stops before starting anything
    (tmp_path / "bin/curl").chmod(0o755)
    base = {k: v for k, v in os.environ.items() if k not in ("RIVER_API_KEY", "GRADUATE_OWNED_BACKEND")}
    r = subprocess.run(
        [tmp_path / "scripts/demo.sh", "--offline"],
        env={**base, **env, "PATH": f"{tmp_path}/bin:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "is taken" in r.stdout and f"{said} (GRADUATE_OWNED_BACKEND=" in r.stdout
    assert ("WARNING: RIVER_API_KEY is set" in r.stdout) == warns
