"""The modules' own `python -m` self-checks, run as tests so CI and `pytest -q` cover them without copying them."""

import subprocess
import sys
from importlib.util import find_spec

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "graduate.reward",  # exit-code reward, pytest summary parser
        "graduate.registry",  # state machine, consent gate, concurrent writers
        "graduate.watcher --check",  # READY flip at N verified runs
        "graduate.router.app",
        "graduate.router.sessionlog",
        "graduate.router.metrics",
        "graduate.escalator",  # reset, rerun on frontier, demote at the fail limit
        pytest.param(  # SFT chat and wire records (#21): renders with River's SDK
            "graduate.registrar.dataset --check",
            marks=pytest.mark.skipif(
                not find_spec("river_client"), reason="needs .[train], Python 3.12"
            ),
        ),
    ],
)
def test_self_check(module, tmp_path):
    r = subprocess.run(
        [sys.executable, "-m", *module.split()],
        cwd=tmp_path,  # anything a check writes lands here
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr
