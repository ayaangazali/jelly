#!/usr/bin/env bash
# Corpus (#6): broken states through `graduate run` with frontier routing, under hard caps. See docs/corpus.md.
# Needs the router on :4141 started from the repo root (its metrics.jsonl is the call and cost counter).
#   CAP_CALLS=400 CAP_USD=6 STATES="01 ... 08" CORPUS_DIR=/home/ubuntu/jelly-corpus scripts/corpus.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CAP_CALLS=${CAP_CALLS:-400} CAP_USD=${CAP_USD:-6}
STATES=${STATES:-01 02 03 04 05 06 07 08}
CORPUS_DIR=${CORPUS_DIR:-/home/ubuntu/jelly-corpus}

touch metrics.jsonl ledger.jsonl
base=$(wc -l <metrics.jsonl)
spent() { tail -n +$((base + 1)) metrics.jsonl | jq -rs '"\(length) \(map(.cost_usd) | add // 0 | . * 1e6 | round / 1e6)"'; }
under() { read -r c u <<<"$(spent)" && [ "$c" -lt "$CAP_CALLS" ] && jq -en "$u < $CAP_USD" >/dev/null; }

# Estimate, printed before any call (the captain's budget order): measured per-call cost and calls per session if metrics.jsonl has frontier rows, else
# 12 calls of 25k prompt tokens (80% cached) and 400 output tokens at prices.json's frontier rates.
# Object values are parenthesized: jq 1.7 (CI) rejects `{k: a / b}`.
jq -rn --slurpfile m metrics.jsonl --slurpfile p prices.json --argjson n "$(wc -w <<<"$STATES")" '
  ($m | map(select(.upstream == "frontier"))) as $f | $p[0].frontier as $r
  | if ($f | length) > 0
    then {src: "measured", calls: (($f | length) / ($f | map(.session_id) | unique | length)), usd: (($f | map(.cost_usd) | add) / ($f | length))}
    else {src: "assumed", calls: 12, usd: ((5000 * $r.input + 20000 * $r.cached_input + 400 * $r.output) / 1e6)} end
  | "estimate (\(.src), \($r.model)): \($n) sessions x \(.calls | ceil) calls = \($n * .calls | ceil) calls, USD \($n * .calls * .usd * 1000 | round / 1000)"'
echo "caps: $CAP_CALLS calls, USD $CAP_USD"

capped=
for n in $STATES; do
  under || {
    capped=1
    break
  }
  scripts/reset-demo.sh "$n"
  graduate run --task-file "demo-repo/tasks/$n.json" --repo demo-repo --timeout 600 &
  run=$!
  while kill -0 $run 2>/dev/null; do # watchdog: a cap hit mid-session kills OpenCode's process group
    under || {
      capped=1
      oc=$(pgrep -P $run) && kill -KILL -- "-$oc" || true
    }
    sleep 1
  done
  wait $run || true # a failed verification is a kept negative example
  [ -z "$capped" ] || break
done
read -r c u <<<"$(spent)"
echo "${capped:+CAP HIT: }spent $c calls, USD $u"
scripts/reset-demo.sh clean
# The classifier (#20) may not be on main: every corpus row is the demo task type by construction.
jq -c 'if .task_type == "unknown" then .task_type = "fix-failing-test" else . end' ledger.jsonl >ledger.tmp
# Stage: the live ledger keeps 4 verified rows plus every failure; the rest wait in backups/.
# Split before any watcher sees the ledger: READY at 5 verified never flips back.
mkdir -p backups
jq -cs 'map(select(.exit_code == 0))[4:][]' ledger.tmp >backups/stage-ledger.jsonl
jq -cs 'map(select(.exit_code == 0))[:4] + map(select(.exit_code != 0)) | .[]' ledger.tmp >ledger.jsonl
rm ledger.tmp registry.json 2>/dev/null || true
python -m graduate.watcher --once
jq -r '.task_types | to_entries[] | "\(.key): \(.value.state), \(.value.verified_runs) verified"' registry.json

jq -rs 'map(select(.exit_code == 0)) as $v | if $v == [] then "baseline: no verified runs" else "baseline over \($v | length) verified: " + (
  ["turns", "tool_calls", "input_tokens", "cached_input_tokens", "output_tokens", "cost_usd", "wall_secs"]
  | map(. as $k | "\($k) \($v | map(.[$k]) | add / length * 1000 | round / 1000)") | join(", "))
  + ", cached share \(($v | map(.cached_input_tokens) | add) / ([1, ($v | map(.input_tokens) | add)] | max) * 100 | round)%" end' \
  ledger.jsonl backups/stage-ledger.jsonl

tgz=backups/corpus-$(date -u +%Y%m%dT%H%M%SZ).tgz
tar czf "$tgz" ledger.jsonl sessions registry.json metrics.jsonl prices.json backups/stage-ledger.jsonl
# Tarball plus uncompressed files: the #21 dataset lane and the #7 pre-train read the files in place.
mkdir -p "$CORPUS_DIR"
cp -r "$tgz" ledger.jsonl sessions registry.json metrics.jsonl prices.json backups/stage-ledger.jsonl "$CORPUS_DIR"/
echo "backup: $tgz, copied to $CORPUS_DIR"
