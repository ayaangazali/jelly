# Demo repo

`demo-repo/` is the stage for the one task type, `fix-failing-test`. It is a tiny pure-Python package (`calc/mod_01.py` … `mod_10.py`, one test file each, only pytest needed).

## Broken states

```bash
scripts/reset-demo.sh 05      # plant broken state 05: tests/test_mod_05.py fails, the other 9 pass
scripts/reset-demo.sh clean   # back to green: 10 passed
```

- Each state changes one line in `calc/mod_NN.py` (a wrong operator or constant), so exactly one test fails.
- The script first restores `demo-repo/` to `HEAD`: it drops edits, untracked files and `__pycache__`, and keeps `.venv/`. Running it twice gives the same tree.
- It works from any directory and in any clone. The planted bugs live in `scripts/reset-demo.sh`, outside `demo-repo/`, so the agent's working tree does not contain the answer.
- The prompt and verify command for each state are in `demo-repo/tasks/NN.json`. Run the verify command from `demo-repo/`.

States are data in the script, not `broken/NN` git branches as the issue first planned. Branches would drift from `main` and need their own maintenance.

## Setup and timing

```bash
cd demo-repo && python3 -m venv .venv && .venv/bin/pip install -q pytest
```

The same two commands are in `demo-repo/.superset/config.json`.

Measured 2026-09-27 on the fleet host, with no pip cache (`PIP_NO_CACHE_DIR=1`): cold `git clone` from GitHub, then `reset-demo.sh 05`, venv, pytest install and `pytest -q tests/test_mod_05.py` took **6.9 s** in total. The target was under 60 s. The full suite runs in about 0.05 s.

## OpenCode

`demo-repo/opencode.json` defines one provider, `graduate`. It uses `@ai-sdk/openai-compatible` with `baseURL` `http://localhost:4141/v1` (the router). The API key is `{env:GRADUATE_SESSION}`, which is the session id (see `graduate/contracts.md`). The default model is `graduate/graduate`.

OpenCode **1.18.32** is installed on the fleet host with the official user-level installer (`curl -fsSL https://opencode.ai/install | bash`, binary at `~/.opencode/bin/opencode`). `opencode debug config` run in `demo-repo/` loads the provider and resolves the key from the environment.
