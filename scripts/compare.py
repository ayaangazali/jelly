"""Frontier vs owned from ledger rows only (#118): python scripts/compare.py LEDGER [--prices PRICES_JSON]

Per task type and arm: n, mean turns, mean tool calls, mean cost and pass rate, each followed by the session ids
behind it. Frontier baseline = verified frontier sessions (contracts §2: exit 0, not an escalation rerun). Owned =
`routed_to: owned` rows with exit 0; a failed owned row counts against the pass rate and nowhere else.

Frontier cost is the ledger's cost_usd. Owned cost is shown on both bases: River list (each row's tokens priced with
the `owned` block of --prices, contracts §9, default prices.json else fixtures/prices.example.json, since the ledger's
cost_usd used whatever prices the writer had) and local ($0 marginal, plus the training wall time from the newest
`graduated` event in the registry.json beside the ledger, when there is one).

Refuses stub data (exit 1): any row with exactly the usage scripts/stub-upstream.py serves, or an upstream-auth.log
beside the ledger. Not the model id: graduate init's prices.json names the same frontier model as the stub (#128).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stub_served(r):
    """scripts/stub-upstream.py answers every call with usage 25000 input, 20000 cached, 40 output."""
    # mirrors the stub's hardcoded usage; change both together (tests/compare/stub.jsonl is one such row)
    calls, rest = divmod(r["output_tokens"], 40)
    return calls > 0 and not rest and (r["input_tokens"], r["cached_input_tokens"]) == (25000 * calls, 20000 * calls)


def river_usd(r, p):
    """Contracts §9 at the `owned` block's prices."""
    fresh = r["input_tokens"] - r["cached_input_tokens"]
    return (fresh * p["input"] + r["cached_input_tokens"] * p["cached_input"] + r["output_tokens"] * p["output"]) / 1e6


def mean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else None


def fmt(v, template):
    return "n/a" if v is None else template.format(v)


def ids(rows):
    return ", ".join(r["session_id"] for r in rows) or "none"


def training_secs(registry, task_type):
    """(seconds, event text) from the newest `graduated` event, which the trainer writes as '... in 612.3 s.'"""
    if not registry.exists():
        return None, "no registry.json beside the ledger"
    for e in json.loads(registry.read_text(encoding="utf-8"))["events"]:  # newest first
        m = re.search(r" in ([\d.]+) s\.$", e["text"])
        if e["kind"] == "graduated" and e["task_type"] == task_type and m:
            return float(m[1]), f'registry.json {e["ts"]}: "{e["text"]}"'
    return None, "no graduated event with a time in registry.json"


def main(path, prices):
    ledger = Path(path)
    owned_prices = json.loads((ROOT / prices).read_text(encoding="utf-8"))["owned"]
    rows = [
        json.loads(l)
        for l in ledger.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    stub = [r["session_id"] for r in rows if stub_served(r)]
    if stub or (ledger.parent / "upstream-auth.log").exists():
        why = (
            f"the stub's usage on {', '.join(stub)}"
            if stub
            else "upstream-auth.log beside the ledger"
        )
        print(
            f"stub data, not a result ({why}: served by scripts/stub-upstream.py)",
            file=sys.stderr,
        )
        return 1
    for r in rows:
        r["river_usd"] = river_usd(r, owned_prices)
    print(f"ledger: {path} ({len(rows)} rows)")
    print(f"owned River list prices: {prices} owned block, {owned_prices['model']}, per 1M tokens: "
          f"input ${owned_prices['input']}, cached ${owned_prices['cached_input']}, output ${owned_prices['output']}")
    for task_type in sorted({r["task_type"] for r in rows}):
        of_type = [r for r in rows if r["task_type"] == task_type]
        arms = {
            "frontier": [
                r
                for r in of_type
                if r["routed_to"] == "frontier" and r["escalated_from"] is None
            ],
            "owned": [r for r in of_type if r["routed_to"] == "owned"],
        }
        passed = {
            arm: [r for r in tried if r["exit_code"] == 0]
            for arm, tried in arms.items()
        }
        print(f"\n{task_type}")
        for arm, tried in arms.items():
            ok = passed[arm]
            rate = f"{len(ok)}/{len(tried)}" + (
                f" ({100 * len(ok) / len(tried):.0f}%)" if tried else ""
            )
            print(
                f"  {arm}: n {len(ok)}, mean turns {fmt(mean(ok, 'turns'), '{:.2f}')}, "
                f"mean tool calls {fmt(mean(ok, 'tool_calls'), '{:.2f}')}, mean cost {fmt(mean(ok, 'river_usd' if arm == 'owned' else 'cost_usd'), '${:.6f}')}"
                f"{' (River list)' if arm == 'owned' else ''}, pass rate {rate}"
            )
            print(f"    passed, in the means: {ids(ok)}")
            print(
                f"    failed, pass rate only: {ids([r for r in tried if r['exit_code'] != 0])}"
            )
        secs, source = training_secs(ledger.parent / "registry.json", task_type)
        print(
            f"  owned, local: mean cost $0 marginal; training wall time {fmt(secs, '{:.1f} s')} ({source})"
        )
        reruns = [
            r
            for r in of_type
            if r["routed_to"] == "frontier" and r["escalated_from"] is not None
        ]
        print(f"  escalation reruns, in neither arm: {ids(reruns)}")
        cached = [r for r in of_type if r["routed_to"] == "cache"]
        print(f"  cache sessions, in neither arm: {ids(cached)}")
        f, o = passed["frontier"], passed["owned"]
        if f and o:
            ft, ot, fc, oc = (
                mean(f, "turns"),
                mean(o, "turns"),
                mean(f, "cost_usd"),
                mean(o, "river_usd"),
            )
            print(
                f"  fewer turns: {'yes' if ot < ft else 'no'} (owned {ot:.2f} vs frontier {ft:.2f}); "
                f"lower cost: River list {'yes' if oc < fc else 'no'} (${oc:.6f} vs ${fc:.6f}), local yes ($0 marginal)"
            )
        else:
            print("  fewer turns, lower cost: n/a (an arm has no passing rows)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ledger")
    ap.add_argument("--prices", default="prices.json" if (ROOT / "prices.json").exists() else "fixtures/prices.example.json")
    args = ap.parse_args()
    sys.exit(main(args.ledger, args.prices))
