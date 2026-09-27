"""scripts/compare.py (#118): the issue's tests 1-4 on the fixture ledgers in tests/compare/."""

import json
import shutil
import subprocess
import sys

from conftest import ROOT

FIXTURES = ROOT / "tests/compare"


def compare(ledger):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/compare.py"),
            str(ledger),
            "--prices",
            "fixtures/prices.example.json",
        ],
        capture_output=True,
        text=True,
    )


def test_each_arm_prints_its_numbers_and_row_ids():
    out = compare(FIXTURES / "ledger.jsonl").stdout.splitlines()
    assert out[1] == (
        "owned River list prices: fixtures/prices.example.json owned block, Qwen3.6-35B-A3B-FP8, per 1M tokens: "
        "input $0.33, cached $0.066, output $0.82"
    )
    frontier = out.index(
        "  frontier: n 3, mean turns 6.67, mean tool calls 5.67, mean cost $0.005935, pass rate 3/3 (100%)"
    )
    assert (
        out[frontier + 1]
        == "    passed, in the means: sess-5e0a3c7b91d2, sess-a17f40c2e6b8, sess-c93b2d58f04e"
    )
    owned = out.index(
        "  owned: n 1, mean turns 7.00, mean tool calls 6.00, mean cost $0.003414 (River list), pass rate 1/2 (50%)"
    )
    assert out[owned + 1 : owned + 3] == [
        "    passed, in the means: sess-0d6e8f1a4b73",
        "    failed, pass rate only: sess-f2b85e9c1a07",
    ]
    assert "training wall time 412.6 s" in out[owned + 3]
    assert out[owned + 4] == "  escalation reruns, in neither arm: sess-7b4c1e02d9a5"
    assert out[owned + 5] == "  cache sessions, in neither arm: none"
    assert out[owned + 6].startswith(
        "  fewer turns: no (owned 7.00 vs frontier 6.67); lower cost: River list yes"
    )


def test_rerun_is_byte_identical():
    first, second = (
        compare(FIXTURES / "ledger.jsonl"),
        compare(FIXTURES / "ledger.jsonl"),
    )
    assert first.returncode == 0 and first.stdout == second.stdout


def test_failed_owned_row_is_excluded_from_the_means():
    # The failed row (sess-f2b85e9c1a07: 4 turns, 3 tool calls) would pull the owned means to 5.50 and 4.50.
    out = compare(FIXTURES / "ledger.jsonl").stdout
    assert (
        "owned: n 1, mean turns 7.00, mean tool calls 6.00, mean cost $0.003414" in out
    )
    assert "in the means: sess-0d6e8f1a4b73\n" in out


def test_stub_data_is_refused(tmp_path):
    stub = compare(FIXTURES / "stub.jsonl")
    assert (stub.returncode, stub.stdout) == (1, "")
    assert stub.stderr.startswith("stub data, not a result")

    shutil.copy(FIXTURES / "ledger.jsonl", tmp_path)
    (tmp_path / "upstream-auth.log").write_text("Bearer sk-stub\n")
    auth = compare(tmp_path / "ledger.jsonl")
    assert (auth.returncode, auth.stdout) == (1, "")
    assert auth.stderr.startswith("stub data, not a result")


def test_real_run_on_the_init_default_model_is_accepted(tmp_path):
    # graduate init copies fixtures/prices.example.json, whose frontier model is the stub's id (#128)
    ledger = (FIXTURES / "ledger.jsonl").read_text().replace('"gpt-5-mini"', '"gpt-5.6-terra"')
    (tmp_path / "ledger.jsonl").write_text(ledger)
    r = compare(tmp_path / "ledger.jsonl")
    assert r.returncode == 0, r.stderr
    assert "pass rate 3/3" in r.stdout


def test_a_cache_session_is_in_neither_arm(tmp_path):
    """#144: a session replayed from the cache moves no arm's numbers and is listed on its own line."""
    rows = (FIXTURES / "ledger.jsonl").read_text().splitlines()
    cached = json.loads(rows[0]) | {"session_id": "sess-00000000cafe", "routed_to": "cache", "cost_usd": 0.0}
    outs = []
    for name, extra in (("before", []), ("after", [json.dumps(cached)])):
        (tmp_path / name).mkdir()
        (tmp_path / name / "ledger.jsonl").write_text("\n".join(rows + extra) + "\n")
        outs.append(compare(tmp_path / name / "ledger.jsonl").stdout.splitlines()[1:])  # [0] is the path and row count
    before, after = outs
    line = before.index("  cache sessions, in neither arm: none")
    assert after[line] == "  cache sessions, in neither arm: sess-00000000cafe"
    assert after[:line] + after[line + 1 :] == before[:line] + before[line + 1 :]
