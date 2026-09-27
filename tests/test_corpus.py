"""scripts/corpus.sh's spend caps on a fake `graduate run` whose agent writes metrics rows like the router does."""

import json
import os
import re
import shutil
import subprocess
import sys

from conftest import ROOT

# Stands in for `graduate run`: its agent is a child in its own session (as runner.run starts OpenCode), one
# metrics.jsonl row at $0.01 per model call; then a verified ledger row.
GRADUATE = f"""#!{sys.executable}
import json, os, subprocess, sys
n = sys.argv[sys.argv.index("--task-file") + 1][-7:-5]
open("started.txt", "a").write(n + "\\n")
row = json.dumps({{"session_id": "sess-" + n, "upstream": "frontier", "cost_usd": 0.01}})
agent = f"import time\\ntime.sleep(0.3)\\nfor _ in range({{os.environ['CALLS']}}):\\n    open('metrics.jsonl', 'a').write({{row!r}} + '\\\\n'); time.sleep(0.02)"
subprocess.run([sys.executable, "-c", agent], start_new_session=True)
ledger = json.loads(open({str(ROOT / "fixtures/ledger.example.jsonl")!r}).readline())
open("ledger.jsonl", "a").write(json.dumps(dict(ledger, session_id="sess-" + n)) + "\\n")
"""


def corpus(tmp, calls, **caps):
    """One scripts/corpus.sh run in `tmp` (never the checkout: it rewrites ledger.jsonl and registry.json)."""
    for f in ("scripts/corpus.sh", "fixtures/prices.example.json"):
        shutil.copy(ROOT / f, tmp / ("prices.json" if f.startswith("fixtures") else f))
    (tmp / "scripts/reset-demo.sh").write_text("#!/bin/sh\n")
    (tmp / "bin/graduate").write_text(GRADUATE)
    for f in ("scripts/reset-demo.sh", "bin/graduate"):
        (tmp / f).chmod(0o755)
    env = {
        "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}",
        "PYTHONPATH": str(ROOT),
        "CALLS": str(calls),
        "CORPUS_DIR": str(tmp / "corpus"),
        **caps,
    }
    out = subprocess.run(
        [tmp / "scripts/corpus.sh"], env=env, capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    started = (tmp / "started.txt").read_text().split()
    (tmp / "started.txt").unlink()
    return out.stdout, started


def test_corpus_caps_stop_the_next_session_and_a_runaway_one(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "sessions").mkdir()  # the router's session logs, tarred into the backup
    # corpus.sh runs `python -m graduate.watcher`
    (tmp_path / "bin/python").symlink_to(sys.executable)
    past = [
        {"session_id": f"sess-p{i % 2}", "upstream": "frontier", "cost_usd": 0.01}
        for i in range(8)
    ]
    (tmp_path / "metrics.jsonl").write_text("".join(json.dumps(m) + "\n" for m in past))

    # 4 calls a session, measured from the past 2 sessions, as each session then spends. 01 and 02 run; 02 ends over
    # the cap, so 03 never starts.
    out, started = corpus(tmp_path, 4, STATES="01 02 03", CAP_CALLS="6")
    assert "3 sessions x 4 calls = 12 calls, USD 0.12" in out, out
    assert started == ["01", "02"] and "CAP HIT: spent 8 calls, USD 0.08" in out, out
    # A runaway agent is killed within a second of crossing the cap, and nothing starts after it.
    out, started = corpus(tmp_path, 500, STATES="01 02", CAP_USD="0.05")
    spent = int(re.search(r"CAP HIT: spent (\d+) calls", out)[1])
    assert started == ["01"] and 5 <= spent < 100, out
