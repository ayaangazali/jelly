"""`graduate results` (#60): the dashboard's /state, frozen to results/state.json from this directory's ledger,
registry and trace. No key, no network: serve the repo root with any static server and open
/ui/index.html?state=/results/state.json (the showcase is #/show)."""

import argparse
import json
from pathlib import Path

from graduate.router.state import build_state


def main():
    ap = argparse.ArgumentParser(prog="graduate results", description=__doc__)
    ap.add_argument("--out", default="results/state.json")
    out = Path(ap.parse_args().out)
    state = build_state()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    runs = len(state["ledger"])
    print(f"wrote {out}: {len(state['registry']['task_types'])} task types, {runs} ledger rows, ${state['totals']['saved_usd']} saved (est.)")
    print(f"view: python -m http.server 8000, then http://localhost:8000/ui/index.html?state=/{out.as_posix()}#/show")
