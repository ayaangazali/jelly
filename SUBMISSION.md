# GRADUATE

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

- **Your model on a repeat: passes.** Broken state 07 is one of the 8 states the owned model trained on. After graduation it routes to the owned model, which fixes it: verified, exit 0, zero frontier calls. That is a repeat of a trained task, not a held-out result.
- **Your model on a new state: fails, and the safety path catches it (headline).** On broken state 09, which it never saw, the owned session fails verification (exit 1). The escalator reruns it on the frontier, which passes (exit 0), and the failure is kept as a negative example. The user gets a passing result. The owned model also fails held-out 10.
- **Savings: n/a.** With no OpenAI credit, the owned model learned from 8 scripted stub sessions, and the frontier side of every comparison is the stub. So there is no real baseline, and we claim no savings ratio.
- **Frontier numbers are stub numbers.** The OpenAI key answers `429 insufficient_quota`, so every frontier session ran against `scripts/stub-upstream.py`, with zero OpenAI calls. The pitch targets output tokens, because prompt caching can't cut them. We have no real measurement of that today.

## Sponsors, and exactly how each is used

- **River**: the key authenticates, but the account has no credits (`RESOURCE_EXHAUSTED billing: insufficient_funds`). So the same trainer interface (`train(chats, name, log)` / `complete(model, messages, tools)`) trains and serves locally, and `GRADUATE_OWNED_BACKEND=river` swaps River in. `river-client`'s renderer builds the training records (`graduate/registrar/dataset.py`). The Exit Code RL spike (#10, [`docs/river-rl.md`](docs/river-rl.md)) is River's `rl.Env` shape, with the pytest exit code as the reward, run locally.
- **Memorable**: `memorable recall "<task>" --single` names the task type (`graduate/router/classify.py`, with a normalized-prompt hash as the fallback), and `memorable ingest` records every verified session (`graduate/memorable/bridge.py`). It runs on Ayaan's machine, which is logged in. The build host has no Memorable CLI, so the offline runs used the fallback and skipped ingest.
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
scripts/demo.sh --offline --use-checkpoint /home/ubuntu/jelly-corpus/checkpoints/fix-failing-test-v3   # zero OpenAI calls; click Approve on http://localhost:4141/?present
make record                                                                                           # the same run, filmed to docs/recordings/offline-rehearsal.mp4
```

### If credit arrives

```bash
(set -a; . ~/super.env; set +a; scripts/live.sh)
```

This one command, about 25 minutes:
1. A 1-token credit probe. Without credit it refuses before touching anything (`refused: no credit`).
2. The real corpus: `scripts/corpus.sh` on broken states 01–08, into `/home/ubuntu/jelly-corpus-live`, capped at USD 6 and 400 calls.
3. A retrain on that corpus: `graduate train fix-failing-test --corpus`.
4. The live demo on the new checkpoint, filmed by `scripts/record.py`, which runs `scripts/demo.sh`. The results land in `docs/results.md` and the video is labelled "live run".

`scripts/live.sh --offline` runs the same chain against the stub.

## Honest limits

- **No savings claimed.** The owned model passes one repeat of a trained task (07), fails two others (06, 08) and fails the held-out states (09, 10). The frontier side is a stub, so no ratio means anything. What the demo shows working is graduation, verification and escalation.
- **No real frontier numbers.** There was no OpenAI credit, so every frontier session in the results and the recording is the stub.
- **The owned model is a local stand-in for River.** Qwen2.5-Coder-0.5B with LoRA, trained on this machine's CPU (~10 min) because the River account has no credits.
- **No model is trained during the demo.** The demo graduates on a checkpoint trained beforehand (`--use-checkpoint`) and says so on screen. Approve still starts a real training job, which the demo stops.
- **One task type, one small repo, 5 verified runs.** How many runs a task type needs is an open question. Every session is verified, so a wrong guess costs latency, not correctness.
