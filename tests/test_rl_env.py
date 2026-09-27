import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("river_client")

from graduate.rl_env import ExitCodeEnv


def test_reward_is_the_verify_exit_code(tmp_path):
    shutil.copytree(Path(__file__).parent.parent / "demo-repo", tmp_path / "01", ignore=shutil.ignore_patterns(".venv"))
    env = ExitCodeEnv(tmp_path)
    score = lambda text: asyncio.run(env.reward(SimpleNamespace(final_text=text), "01"))
    assert score("```python\ndef add(a, b):\n    return a + b\n```") == 1.0
    assert score("```python\ndef add(a, b):\n    return a - b\n```") == 0.0
    assert score("add returns a + b") == 0.0
    assert "tests/test_mod_01.py" in asyncio.run(env.reset("01"))[0]["content"]
