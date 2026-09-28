"""Exit-code reward (#14). Episode shape: graduate/contracts.md §10."""

import re


def reward(ep: dict[str, int]) -> float:
    if ep["exit_code"] == 0:
        r = 1.0
    else:  # partial credit for moving in the right direction
        r = 0.3 * ep["tests_passed"] / max(ep["tests_total"], 1)
    r -= 0.02 * ep["tool_calls"]  # efficiency pressure
    r -= 0.10 * ep["files_touched_outside_scope"]  # no collateral damage
    return max(r, 0.0)


def parse_pytest_summary(output: str) -> tuple[int, int]:
    counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|error)", output)}
    return counts.get("passed", 0), sum(counts.values())  # (passed, total)


if __name__ == "__main__":
    ep = {
        "exit_code": 0,
        "tests_passed": 1,
        "tests_total": 1,
        "tool_calls": 3,
        "files_touched_outside_scope": 0,
    }
    assert abs(reward(ep) - 0.94) < 1e-9  # pass: fixtures/rl-episode.example.json
    fail = {**ep, "exit_code": 1, "tests_passed": 2, "tests_total": 3, "tool_calls": 0}
    assert abs(reward(fail) - 0.2) < 1e-9  # partial credit
    assert reward({**fail, "tests_passed": 0, "tests_total": 0}) == 0.0  # zero tests
    heavy = {**ep, "tool_calls": 40, "files_touched_outside_scope": 5}
    assert reward(heavy) == 0.0  # penalties floored, never negative
    assert parse_pytest_summary("3 passed in 0.01s") == (3, 3)
    assert parse_pytest_summary("1 failed, 2 passed in 0.02s") == (2, 3)
    assert parse_pytest_summary("no tests ran in 0.01s") == (0, 0)
    print("reward: ok")
