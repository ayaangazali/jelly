#!/usr/bin/env bash
# make e2e (#59) on a stub upstream: a 4-call session passes, then each cap stops it within 3 calls or $0.02.
#   scripts/e2e-offline.sh STUB_BASE_URL OUT_DIR       (scripts/corpus-dryrun.sh calls it with its stub)
set -euo pipefail
url=$1 out=$2
e2e() { # e2e PATTERN [VAR=value]: the last line of make e2e, run from OUT_DIR, matches PATTERN
  { env -C "$out" OPENAI_BASE_URL="$url" OPENAI_API_KEY=sk-stub "${@:2}" python -m graduate.e2e || true; } |
    tee -a "$out/e2e.txt" | tail -1 | grep -q "$1" || {
    echo "FAIL: make e2e ${*:2}: see $out/e2e.txt" >&2
    exit 1
  }
}
e2e "^e2e sess-.* exit 0 · 4 calls"
e2e "^CAP HIT: .* · [23] calls" E2E_CAP_CALLS=3
e2e "^CAP HIT: .* · [23] calls" E2E_CAP_USD=0.02
