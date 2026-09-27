#!/usr/bin/env bash
# The 3-minute demo as one command (#31): 4 of 5 -> broken 05 -> READY -> Approve -> GRADUATED -> broken 09 on your
# model -> forced failure on broken 10 -> escalation -> numbers into docs/results.md. Unattended apart from the Approve click.
#
#   scripts/demo.sh [--offline] [--use-checkpoint PATH] [--auto-approve]
#
# live (default)    the router's upstream comes from this environment (OPENAI_API_KEY, OPENAI_BASE_URL) or .env; the key
#                   stays in the router's process only: (set -a; . ~/super.env; set +a; scripts/demo.sh --use-checkpoint ...)
# --offline         the frontier is scripts/stub-upstream.py on :$PORT+1: zero OpenAI calls, and the numbers are stub numbers.
# --use-checkpoint  graduate on a checkpoint trained before the demo instead of waiting for the live training job.
# --auto-approve    POST the consent instead of waiting for the click on the dashboard (unattended runs).
#
# Needs an activated .venv, OpenCode and a free :$PORT (default 4141; another port keeps other lanes' routers on 4141
# untouched). The staged 4-of-5 corpus comes from $CORPUS_DIR (live default
# /home/ubuntu/jelly-corpus, see docs/corpus.md; offline default backups/stub-corpus, built on first use).
# Earlier run state in the repo root moves to backups/demo-<time>/before/ first; the transcript is backups/demo-<time>/demo.log.
set -euo pipefail
cd "$(dirname "$0")/.."
offline= checkpoint= auto=
while [ $# -gt 0 ]; do
 case $1 in
 --offline) offline=1 ;;
 --use-checkpoint)
  checkpoint=${2:?--use-checkpoint needs a path}
  shift
  ;;
 --auto-approve) auto=1 ;;
 *)
  echo "usage: scripts/demo.sh [--offline] [--use-checkpoint PATH] [--auto-approve]" >&2
  exit 2
  ;;
 esac
 shift
done
CORPUS_DIR=${CORPUS_DIR:-$([ -n "$offline" ] && echo backups/stub-corpus || echo /home/ubuntu/jelly-corpus)}
PORT=${PORT:-4141}
export GRADUATE_ROUTER=http://localhost:$PORT OPENCODE_CONFIG_CONTENT='{"provider":{"graduate":{"options":{"baseURL":"http://localhost:'$PORT'/v1"}}}}'
T=fix-failing-test
out=backups/demo-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$out/before"
exec > >(tee "$out/demo.log") 2>&1

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() {
 echo "FAIL: $*" >&2
 exit 1
}
state() { jq -r --arg t $T '.task_types[$t].state // "none"' registry.json 2>/dev/null; }
until_state() { # until_state STATE SECONDS
 for _ in $(seq "$2"); do
  [ "$(state)" = "$1" ] && return
  sleep 1
 done
 die "$T is $(state), waited $2 s for $1"
}
run() { # run NN: plant broken state NN, one `graduate run`
 scripts/reset-demo.sh "$1"
 graduate run --task-file "demo-repo/tasks/$1.json" --repo demo-repo --timeout 600
}

say "reset: earlier state -> $out/before/, demo-repo clean"
! curl -sf localhost:$PORT/healthz >/dev/null || die ":$PORT is taken: stop the other router first"
python -c 'import river_client' 2>/dev/null || die "step 2 builds River training records: pip install -e '.[test,train]' (Python 3.12+)"
for f in ledger.jsonl metrics.jsonl sessions registry.json registry.lock trace.jsonl terminal.log data; do
 [ ! -e $f ] || mv $f "$out/before/"
done
scripts/reset-demo.sh clean
own_prices=
[ -e prices.json ] || {
 cp "$CORPUS_DIR/prices.json" prices.json 2>/dev/null || cp fixtures/prices.example.json prices.json
 own_prices=1
}
pids=()
if [ -n "$offline" ]; then
 python3 scripts/stub-upstream.py $((PORT + 1)) "$out/upstream-auth.log" &
 pids+=("$!")
 export OPENAI_BASE_URL=http://127.0.0.1:$((PORT + 1))/v1 OPENAI_API_KEY=sk-stub
fi
python -m graduate.watcher >"$out/watcher.log" 2>&1 &
pids+=("$!")
uvicorn graduate.router.app:app --port "$PORT" >"$out/router.log" 2>&1 & # router + dashboard
router=$!
pids+=("$router")
trap 'kill "${pids[@]}" 2>/dev/null; [ -z "$own_prices" ] || rm -f prices.json; scripts/reset-demo.sh clean >/dev/null' EXIT
unset OPENAI_API_KEY # only the router holds the key
until curl -sf localhost:$PORT/healthz >/dev/null; do
 kill -0 $router 2>/dev/null || die "router exited: $(cat "$out/router.log")"
 sleep 0.2
done
echo "dashboard: http://localhost:$PORT/   frontier: ${OPENAI_BASE_URL:-from .env or api.openai.com}${offline:+ (STUB, zero OpenAI calls)}"

say "1/6 restore the staged 4-of-5 ledger from $CORPUS_DIR"
if [ ! -e "$CORPUS_DIR/ledger.jsonl" ]; then
 [ -n "$offline" ] || die "no corpus in $CORPUS_DIR: run scripts/corpus.sh first (docs/corpus.md)"
 STATES="01 02 03 04" CORPUS_DIR=$CORPUS_DIR scripts/corpus.sh # 4 stub sessions, once
fi
cp -r "$CORPUS_DIR"/{ledger.jsonl,metrics.jsonl,sessions} .
until_state LEARNING 10 # the watcher counts the restored ledger
jq -r --arg t $T '"\($t): \(.task_types[$t].state), \(.task_types[$t].verified_runs) of 5 verified"' registry.json
base=$(wc -l <ledger.jsonl)

say "2/6 broken state 05 on the frontier: the fifth verified run"
run 05
until_state READY 10
python -m graduate.registrar.dataset $T # the training data the consent screen shows

say "3/6 consent: $T is READY"
if [ -n "$auto" ]; then
 curl -sf -X POST localhost:$PORT/api/consent/$T
 echo
else
 echo ">>> click Approve on the dashboard: http://localhost:$PORT/"
fi
until_state TRAINING 900
echo "training job started, log: data/$T.train.log"

if [ -n "$checkpoint" ]; then
 say "4/6 GRADUATED on checkpoint $checkpoint, trained BEFORE the demo, not by the job that just started"
 # The job consent started would train for ~10 min at ~5 GB beside the served model: stop it (a child of this
 # demo's router, so no other checkout's trainer or agent can match).
 for p in $(pgrep -P "$router" -f "graduate\.registrar\.train $T" || true); do
  kill -9 "$p" && echo "stopped the live training job (pid $p)"
 done
 graduate train "$T" --use-checkpoint "$checkpoint" # records trained_on_runs from the checkpoint (#22)
else
 say "4/6 waiting for the live training job to graduate $T"
 until_state GRADUATED "${TRAIN_WAIT:-3600}"
fi
jq -r --arg t $T '"\($t): \(.task_types[$t].state) on \(.task_types[$t].model)"' registry.json

say "5/6 broken state 09: routed to your model"
n09=$(wc -l <ledger.jsonl)
run 09 || true # the owned session may fail its tests: the escalator reruns it on the frontier
jq -rs --argjson n "$n09" '.[$n:][] | "09: routed_to \(.routed_to), model \(.model), exit \(.exit_code), \(.turns) turns, \(.wall_secs) s\(if .escalated_from then ", rerun of \(.escalated_from)" else "" end)"' ledger.jsonl
[ "$(jq -rs --argjson n "$n09" '.[$n].routed_to' ledger.jsonl)" = owned ] ||
 echo "NOTE: 09 was not served by your model: the router fell back to the frontier (see the trace)"

say "6/6 GRADUATE_FORCE_FAIL=1 on broken state 10: fail, escalate, rerun on the frontier"
GRADUATE_FORCE_FAIL=1 run 10

say "numbers -> docs/results.md"
jq -rs --argjson n "$base" --arg when "$(date -u +%Y-%m-%dT%H:%MZ)" --arg model "$(jq -r .frontier.model prices.json)" \
 --arg how "${checkpoint:+checkpoint $checkpoint, trained before the demo}" --arg stub "$offline" '
  def r: . * 1000 | round / 1000;
  . as $all | (.[:$n + 1] | map(select(.routed_to == "frontier" and .exit_code == 0 and .escalated_from == null))) as $b
  | .[$n:] as $d | ($d | map(select(.prompt | test("mod_09")))[0]) as $a | ($d | map(select(.prompt | test("mod_10")))) as $e
  | map(select(.routed_to == "frontier" and .escalated_from == null)) as $f | map(select(.routed_to == "owned")) as $o
  | [["Output tokens", "output_tokens"], ["Input tokens (cached included)", "input_tokens"], ["Cached input tokens", "cached_input_tokens"],
     ["Cost (USD)", "cost_usd"], ["Turns (model calls)", "turns"], ["Tool calls", "tool_calls"], ["Wall time (s)", "wall_secs"]]
  | map(. as [$label, $k] | ($b | map(.[$k]) | add / length) as $x | $a[$k] as $y
      | "| \($label) | \($x | r) | \($y | r) | \(if $x == 0 then "n/a" else "\(($y - $x) / $x * 100 | round)%" end) |") as $table
  | (if $stub == "1" then "**STUB RUN, NOT REAL NUMBERS.** The frontier was `scripts/stub-upstream.py`: zero OpenAI calls, scripted three-turn sessions and made-up token counts. A live run replaces this section."
     else "Live run. Frontier model `\($model)`, prices from `prices.json` (contracts §9)." end) as $label
  | ["### Last demo run: \($when)", "", $label, "",
     "Baseline: mean of the \($b | length) verified frontier runs before graduation (the staged corpus plus broken state 05), with the provider'"'"'s prompt caching on: \(($b | map(.cached_input_tokens) | add) / ([1, ($b | map(.input_tokens) | add)] | max) * 100 | round)% of their input tokens were cached and billed at the cached rate. After: broken state 09 on the graduated task type, graduated \(if $how == "" then "by the live training job" else "on the \($how)" end).",
     "", "| | Frontier baseline, caching on | Graduated, broken state 09 | Change |", "|---|---|---|---|"] + $table
  + ["", "- 09 served by: `\($a.routed_to)` (`\($a.model)`), exit \($a.exit_code)." + (if $a.routed_to != "owned" then " Owned serving (#37) is not on main yet, so the router fell back to the frontier and the After column is a frontier run." else "" end),
     "- Pass rate: frontier \($f | map(select(.exit_code == 0)) | length) of \($f | length) sessions; owned \($o | map(select(.exit_code == 0)) | length) of \($o | length) (forced failures included).",
     "- Safety path, broken state 10 with `GRADUATE_FORCE_FAIL=1`: owned attempt `\($e[0].session_id)` exit \($e[0].exit_code) (forced_failure \($e[0].forced_failure)); frontier rerun `\($e[1].session_id)` exit \($e[1].exit_code), escalated_from `\($e[1].escalated_from)`. The failed row stays in `ledger.jsonl`; forced failures are not kept as training negatives.",
     "- Task types in the ledger: \($all | group_by(.task_type) | map("`\(.[0].task_type)` \(length)") | join(", ")).",
     "- All sessions (\($all | length)): \($all | map(.cost_usd) | add | r) USD, \($all | map(.output_tokens) | add) output tokens."] | join("\n")' \
 ledger.jsonl >"$out/results.md"
awk -v f="$out/results.md" '/<!-- demo.sh:end -->/ { while ((getline l <f) > 0) print l; skip = 0 } !skip; /<!-- demo.sh:begin -->/ { skip = 1 }' \
 docs/results.md >"$out/results.full.md"
mv "$out/results.full.md" docs/results.md
cat "$out/results.md"

say "checks"
check() { "$@" >/dev/null || die "$*"; }
check jq -se --argjson n "$base" '.[$n] | .exit_code == 0 and .routed_to == "frontier"' ledger.jsonl
check jq -se --argjson n "$base" '.[-2:] | .[0].routed_to == "owned" and .[0].exit_code == 1 and .[1].exit_code == 0 and .[1].escalated_from == .[0].session_id' ledger.jsonl
ids=$(jq -sc --argjson n "$base" '.[$n:] | map(.session_id)' ledger.jsonl)
curl -sf localhost:$PORT/state >"$out/state.json"
check jq -e --argjson ids "$ids" '[.trace[] | select(.session_id as $s | $ids | index($s))] | length > 0' "$out/state.json"
check jq -e '[.trace[].who] | index("Escalator → Runner") and index("Watcher → registry.json")' "$out/state.json"
jq -r --argjson ids "$ids" '"trace events on /state for this run'"'"'s sessions: \([.trace[] | select(.session_id as $s | $ids | index($s))] | length) of \(.trace | length)"' "$out/state.json"
[ -z "$offline" ] || check jq -Rse 'split("\n") | map(select(. != "")) | all(. == "Bearer sk-stub")' "$out/upstream-auth.log"
echo "demo ok: $out/demo.log"
[ ! -t 0 ] || read -rp "The dashboard stays up on :$PORT for the stamp and the savings. Enter stops it. "
