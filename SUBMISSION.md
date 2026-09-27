# GRADUATE

Own Your Intelligence Hackathon (YC, 2026-09-27). The submission is the demo recording, this file and [`docs/results.md`](docs/results.md).

**Problem.** Coding agents pay frontier prices to redo the same kind of task every time, because nothing they do teaches the model anything.

**Mechanism.** A router between the agent and its model counts task types whose sessions pass their tests, and after 5 verified runs (and your approval) trains a small model you own on those sessions, routes that task type to it, verifies every call with the same tests, and falls back to the frontier when a test fails.

## Numbers

In [`docs/results.md`](docs/results.md), which `scripts/demo.sh` rewrites on every run: output tokens, input and cached tokens, cost, turns, wall time and pass rate, before (the frontier with prompt caching on) and after graduation. **Pending a live run: the numbers there now come from the offline stub and are not real.**

## Sponsors, and exactly how each is used

- **River**: the planned trainer and host for the owned model (`river-client` SFT loop, #22; serving adapter, #37). No River key reached us, so River calls run against a fake backend and the owned model is a local stand-in (below). `river-client`'s renderer does build the training records (`graduate/registrar/dataset.py`).
- **Memorable**: `memorable recall "<task>" --single` names the task type (`graduate/router/classify.py`), and `memorable ingest` records every verified session (`graduate/memorable/bridge.py`).
- **OpenAI**: the frontier model and the fallback, reached through the router over Chat Completions.
- **OpenCode**: the agent harness in the demo; its `opencode.json` points at the router.
- **QM**: registers the router as a custom provider, proven against a stub ([`docs/qm-config.md`](docs/qm-config.md)); no live QM demo.

## Run it

```bash
uvx --from git+https://github.com/ayaangazali/jelly graduate up --demo   # the dashboard on fixture data, no key
```

The full demo, from a clone with `.venv` active and OpenCode installed ([README quickstart](README.md#quickstart)):

```bash
scripts/demo.sh --offline --auto-approve --use-checkpoint <path>   # zero OpenAI calls, stub numbers
(set -a; . ~/super.env; set +a; scripts/demo.sh --use-checkpoint <path>)   # live; click Approve on http://localhost:4141/
```

## Honest limits

- **The owned model is a local stand-in for River.** It is a small open model trained with LoRA on CPU on the build host, because no River key arrived.
- **No model was trained during the demo.** The demo graduates on a checkpoint trained beforehand (`--use-checkpoint`) and says so on screen. Approve still starts the training job.
- **Owned serving (#37) may not be wired.** When it is missing, the router logs that and serves the graduated task type from the frontier; `docs/results.md` then says which upstream served each session.
- **The demo's failure is forced.** `GRADUATE_FORCE_FAIL=1` marks the owned attempt failed so the escalation path shows on stage; forced failures are not kept as training negatives.
- **One task type, one small repo, 5 verified runs.** How many runs a task type needs is an open question; every call is verified, so a wrong guess costs latency, not correctness.
