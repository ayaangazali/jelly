# Jelly

Own Your Intelligence Hackathon (YC, 2026-09-27). The submission is the recording, this file and [`docs/results.md`](docs/results.md).

**Problem.** Coding agents pay frontier prices to redo the same kind of task every time, and nothing they do teaches the model anything.

**Mechanism.** A router sits between the agent and its model and counts task types whose sessions pass their tests. After 5 verified runs, and your approval, it trains a small model you own on those sessions and routes that task type to it. The same tests verify every session, and when one fails the session reruns on the frontier.

**Recording.** [`docs/recordings/offline-rehearsal.mp4`](docs/recordings/offline-rehearsal.mp4). It is an **offline rehearsal**, labelled so in every frame: the frontier is a local stub, and the owned model is the real local checkpoint running in real time.

## What works today, end to end

- **Router** (`graduate/router/`): OpenAI Chat Completions passthrough on :4141, plus Anthropic `/v1/messages` for Claude Code (#26). It routes graduated task types to the owned model and fails open to the frontier.
- **Session log**: every model call, per session (the bearer token is the session id), in `sessions/` and `metrics.jsonl`.
- **Verification**: `graduate run` runs the agent (OpenCode), then the task's verify command, and writes one `ledger.jsonl` row per session.
- **Graduation**: the watcher counts verified runs. At 5 the task type is READY; consent starts TRAINING; training ends GRADUATED (`registry.json`, `GRADUATED.md`).
- **Local training and serving**: LoRA SFT of Qwen2.5-Coder-0.5B on CPU from the session log, served back through the router (`graduate/registrar/train.py`, [`docs/pretrained-model.md`](docs/pretrained-model.md)).
- **Escalation**: a failed owned session resets the repo and reruns on the frontier. The failure is kept as a negative example, and repeated failures put the task type on probation.
- **Projector dashboard** (`ui/`): the overview, the showcase (`#/show`), the comparison, presenter mode (`?present`) and Under the hood, a live diagram lit only by real trace events.
- **One-command setup**: `graduate up --demo` (no key), `graduate init`, and `scripts/demo.sh` for the whole 3-minute demo.
- **Tests and CI**: pytest under `tests/` plus module self-checks (`make check && make test`). CI also replays a real OpenCode session and the whole offline demo against the stub, at $0.

## Numbers (from [`docs/results.md`](docs/results.md))

- **Real OpenAI benchmark** ([details](docs/results.md#real-benchmark-openai-frontier-vs-small-vs-river-trained-owned)): frontier OpenAI `gpt-5.5`, small OpenAI `gpt-5.4-mini`, and the River-trained owned model (Qwen3.5-9B LoRA), on held-out states 09 and 10 plus repeat 07. **All three arms passed 3 of 3.** Output tokens a session: `gpt-5.5` 670, `gpt-5.4-mini` 804, owned 820, so **the owned model did not cut output tokens** (+22% vs `gpt-5.5`). Cost a session: $0.281, $0.047, $0.006 (owned 47× cheaper than `gpt-5.5`, at priced, not billed, River rates).
- **Live on the public data, big model to small model:** 5 of 5 sessions verified on `gpt-5.5` (Memorable classified each, agents shared notes through GBrain), River trained a fresh LoRA on those 5 in 95.5 s, and the next held-out states 06, 08 and 09 routed to it and passed with zero frontier calls. 07 was misclassified by Memorable and went, safely, to `gpt-5.5`.
- **`make e2e` passed live** on `gpt-5.4-mini`: exit 0, 13 calls, $0.057. OpenAI spend for all real OpenAI runs: $3.68 at list prices.
- **The big model is real: Claude Haiku 4.5**, via Anthropic's OpenAI-compatible Chat Completions API (OpenAI had no credit). On broken states 01–08 it passed 8 of 8 real OpenCode sessions through the router: mean 7.1 turns, 710 output tokens, $0.176 and 18.3 s a session. That endpoint reports no cached tokens, so this baseline pays full price for input.
- **Your model, retrained on those 8 real sessions (local CPU, Qwen2.5-Coder-0.5B LoRA, 1171 s): passes the repeat, fails both held-out states.** On repeat 07 it passes on its own: exit 0, 6 turns, 326 output tokens, $0 marginal, 126 s. Claude took 7 turns, 734 output tokens, $0.173 and 19 s on the same state. On held-out 09 and 10 it fails verification (exit 1). The escalator reruns both on Claude, and both pass, so the user gets a passing result every time. The River-trained model (Qwen3.5-9B) is reported separately in [`docs/results.md`](docs/results.md#river-the-owned-model-trained-and-served-on-river-qwen35-9b).
- **Savings: not claimed.** One passing repeat out of three owned sessions doesn't support a ratio. The owned model used fewer output tokens on that repeat, and it was about 7× slower on CPU.
- **Spend:** $2.90 of a $3 cap, over 108 calls to Claude, from the ledger and the router's metrics. $0.52 of it was another lane's session that used this router's port by mistake.

## Sponsors, and exactly how each is used

- **River**: the key authenticates, but the account has no credits (`RESOURCE_EXHAUSTED billing: insufficient_funds`). So the same trainer interface (`train(chats, name, log)` / `complete(model, messages, tools)`) trains and serves locally, and `GRADUATE_OWNED_BACKEND=river` swaps River in. `river-client`'s renderer builds the training records (`graduate/registrar/dataset.py`). The Exit Code RL spike (#10, [`docs/river-rl.md`](docs/river-rl.md)) is River's `rl.Env` shape, with the pytest exit code as the reward, run locally.
- **Memorable**: `memorable recall "<task>" --single` names the task type (`graduate/router/classify.py`, with a normalized-prompt hash as the fallback), and `memorable ingest` records every verified session (`graduate/memorable/bridge.py`). It runs where the Memorable CLI is logged in (Ayaan's Mac, [`docs/sponsor-answers.md`](docs/sponsor-answers.md)). The build host has no Memorable CLI, so the offline runs used the fallback and skipped ingest.
- **GBrain**: on every graduation, `GRADUATED.md` is piped to `gbrain put graduated --force` (#28). It fails open when `gbrain` is missing.
- **QM**: the router registers as a custom QM provider, proven against a stub ([`docs/qm-config.md`](docs/qm-config.md)). There is no live QM demo.
- **OpenAI**: the frontier model and the fallback, over Chat Completions. It had no credit today, so it was stubbed.
- **OpenCode**: the agent harness in the demo. `opencode.json` points it at the router.

## Run it

```bash
uvx --from git+https://github.com/ayaangazali/jelly graduate up --demo   # the dashboard on fixture data, no key
```

The full demo runs from a clone with `.venv` active, `pip install -e '.[test,train]'` and OpenCode installed ([README quickstart](README.md#quickstart)):

```bash
GRADUATE_CHECKPOINT=<dir of the fix-failing-test-v3 LoRA adapter>   # where it lives: docs/pretrained-model.md
scripts/demo.sh --offline --use-checkpoint "$GRADUATE_CHECKPOINT"   # zero OpenAI calls; click Approve on http://localhost:4141/
make record ARGS="--offline --auto-approve --use-checkpoint $GRADUATE_CHECKPOINT"   # the same run, filmed to docs/recordings/offline-rehearsal.mp4
```

### If credit arrives

```bash
(set -a; . ~/super.env; set +a; scripts/live.sh)
```

This one command, about 25 minutes:
1. A 1-token credit probe. Without credit it refuses before touching anything (`refused: no credit`).
2. The real corpus: `scripts/corpus.sh` on broken states 01–08, into `~/jelly-corpus-live`, capped at USD 6 and 400 calls.
3. A retrain on that corpus: `graduate train fix-failing-test --corpus`.
4. The live demo on the new checkpoint, filmed by `scripts/record.py`, which runs `scripts/demo.sh`. The results land in `docs/results.md` and the video is labelled "live run".

`scripts/live.sh --offline` runs the same chain against the stub.

## Honest limits

- **No savings claimed.** On real Claude Haiku 4.5 sessions, the locally retrained owned model passes one repeat of a trained task (07) and fails both held-out states (09, 10). What works end to end is graduation, verification and escalation.
- **The recording is not all real.** The offline rehearsal video uses the stub frontier. The real Claude numbers are in [`docs/results.md`](docs/results.md#real-runs-claude-haiku-45-as-the-big-model).
- **The owned model is a local stand-in for River.** Qwen2.5-Coder-0.5B with LoRA, trained on this machine's CPU (~10 min) because the River account has no credits.
- **No model is trained during the demo.** The demo graduates on a checkpoint trained beforehand (`--use-checkpoint`) and says so on screen. Approve still starts a real training job, which the demo stops.
- **The owned model is cheaper, not shorter.** On the OpenAI bench it passes like `gpt-5.5` at about 1/47 of the cost, but writes more output tokens, not fewer. 3 runs per arm is too few for a pass rate.
- **One task type, one small repo, 5 verified runs.** How many runs a task type needs is an open question. Every session is verified, so a wrong guess costs latency, not correctness.
