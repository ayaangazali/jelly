---
title: "Architecture"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Components, data flow, schemas, repo layout. Build from this file."
updated: "2026-09-26"
related:
  - 03-build/hour-by-hour.md
---

# Architecture

## Design principles

1. **Build no component a sponsor already ships.** No trace recorder (Memorable). No orchestration (Superset/QM). No training infra (River). GRADUATE is the wire between them.
2. **The integration surface is a base URL.** If adoption requires anything more than changing `base_url`, adoption does not happen.
3. **Never trust the small model.** The verifier runs on every graduated call.
4. **Fail open to the frontier model.** Every failure path ends at "the expensive model handles it," so GRADUATE can never make a user's day worse.

---

## System diagram

```
                       ┌──────────────────────────────────────┐
  agent harness  ──────▶            ROUTER (proxy)            │
  (Claude Code,        │  OpenAI-compatible /v1/chat/completions
   Codex, QM,          │                                      │
   Superset, UFO)      │   classify ──▶ graduated?            │
                       │        │           │                 │
                       │        │ no        │ yes             │
                       └────────┼───────────┼─────────────────┘
                                ▼           ▼
                     frontier model    River owned model
                     (Anthropic/          (OpenAI-compatible
                      OpenAI)              endpoint)
                                │           │
                                └─────┬─────┘
                                      ▼
                                  VERIFIER
                           (run the task's verify cmd)
                                      │
                    pass ─────────────┴───────────── fail
                      │                                │
                      ▼                                ▼
                 Memorable                       ESCALATOR
             (procedure + exit 0)           retry on frontier;
                      │                     log negative example
                      ▼                                │
                   WATCHER ◀───────────────────────────┘
          (cluster into task types, count verified runs)
                      │
              N verified reached
                      ▼
                  REGISTRAR
          build dataset ──▶ River fine-tune / RL job
                      │
                      ▼
              REGISTRY (task_type → model_id)
                      │
                      └──────▶ read by ROUTER
```

---

## Components

### 1. Router (`router/`)

An HTTP server exposing `POST /v1/chat/completions` (OpenAI-compatible). Because River serves owned models through an OpenAI-compatible endpoint, and every frontier provider either is OpenAI-compatible or has a thin adapter, the router can forward either way with the same request shape.

Responsibilities:
- classify the request into a `task_type`
- look up the registry
- forward to graduated model or frontier model
- stream the response back unchanged
- emit a metrics record for every call

Keep it stateless apart from a registry read. Registry can be a JSON file for the hackathon.

**Classification, v1 (do not overbuild this):**
1. Exact match on a normalized prompt template hash.
2. Embedding similarity against known task-type centroids, threshold ~0.85.
3. Miss → `unknown`, route to frontier.

Memorable's own retrieval runs exact → lexical → semantic in that order. Mirror it; it is proven and it is cheap.

### 2. Watcher (`watcher/`)

Polls Memorable for procedures and their run outcomes (CLI `memorable list` / `memorable show`, or the read-only MCP server, or a direct store read — confirm the fastest path with their team).

Produces, per task type:
```json
{
  "task_type": "fix-failing-test",
  "verified_runs": 7,
  "failed_runs": 2,
  "avg_turns": 16,
  "avg_tool_calls": 5,
  "avg_cost_usd": 0.42,
  "verify_command": "pytest tests/",
  "state": "READY"
}
```

### 3. Registrar (`registrar/`)

Builds a training dataset from verified runs and submits it to River.

**Dataset record (SFT):**
```json
{
  "messages": [
    {"role": "system", "content": "<task-type system prompt>"},
    {"role": "user", "content": "<the original request>"},
    {"role": "assistant", "content": "<the winning action sequence>"}
  ],
  "metadata": {
    "task_type": "fix-failing-test",
    "verify_command": "pytest tests/",
    "exit_code": 0,
    "tool_calls": 3,
    "source_procedure": "procedures/89f11bab-fix-failing-auth-test"
  }
}
```

**Dataset record (RL episode):**
```json
{
  "prompt": "<the original request>",
  "trajectory": [ {"tool": "read_file", "args": {...}}, {"tool": "edit", "args": {...}} ],
  "verify_command": "pytest tests/auth",
  "exit_code": 0,
  "tests_passed": 14,
  "tests_total": 14,
  "reward": 0.94
}
```

Reward function lives in `graduate-spec.md` §5. Keep it in one file, `reward.py`, so it can be shown on screen during the pitch.

### 4. Escalator (`escalator/`)

After a graduated call, run the task type's verify command. On non-zero exit:
1. retry the same request on the frontier model
2. return that result to the user (the user never eats the failure)
3. write a negative example
4. increment a failure counter; past a threshold, move the task type to `PROBATION` and stop routing to the graduated model

### 5. Registry (`registry.json`)

```json
{
  "fix-failing-test": {
    "state": "GRADUATED",
    "model_id": "river:ft-graduate-fix-failing-test-001",
    "graduated_at": "2026-09-27T15:40:00Z",
    "trained_on_runs": 7,
    "verified_since_graduation": 12,
    "failures_since_graduation": 1,
    "baseline": {"turns": 16, "tool_calls": 5, "cost_usd": 0.42},
    "current":  {"turns": 3,  "tool_calls": 3, "cost_usd": 0.011}
  }
}
```

This file **is** the demo. The dashboard is just a renderer over it.

### 6. Dashboard (`ui/`)

Single HTML page, polls a `/state` endpoint, renders:
- a card per task type with its state and a progress bar toward the graduation bar
- before/after bars for turns, tool calls and cost
- a live event log (`graduating fix-failing-test…`, `training job submitted`, `routed to owned model`, `verify passed, exit 0`)
- a running total: "$X saved across Y runs"

Keep it one file. No build step. No framework. You have 3h45m.

---

## Data flow, end to end

1. Developer runs a task through their normal agent, pointed at the router.
2. No graduated model exists → frontier model handles it → verifier runs → Memorable records the procedure with exit code.
3. Repeat until N verified runs. Superset runs these in parallel worktrees to build the corpus fast.
4. Watcher flips the type to READY. Registrar builds the dataset and submits to River.
5. River returns a model id. Registry updates to GRADUATED.
6. Next matching request routes to the owned model. Verifier still runs. Metrics recorded.
7. On failure, escalator falls back and records a negative example.

---

## What lives where (privacy posture)

This mirrors the posture the sponsors already take, which matters for the pitch:

- **Traces and file contents:** stay on the machine. Memorable sends only the prompt and allow-listed tool arguments.
- **Training data:** goes to River, because it has to. Be explicit about this in the pitch and make it opt-in per task type.
- **Weights:** owned by the user. River states trained weights are yours to keep, version and serve.
- **Registry:** local JSON, or the GBrain database if you want the GBrain integration.

---

## Repo layout

```
graduate/
├── README.md
├── router/          # OpenAI-compatible proxy + classifier
├── watcher/         # Memorable reader, task-type clustering
├── registrar/       # dataset builder + River client
├── escalator/       # verify, fallback, negative examples
├── reward.py        # the RL reward function (show this on screen)
├── ui/index.html    # dashboard
├── registry.json
└── scripts/
    ├── seed-corpus.sh    # spawn N Superset agents to generate runs
    └── demo.sh           # the scripted demo path
```

Language: Python for watcher/registrar/reward, anything for the router. Do not introduce a build step.
