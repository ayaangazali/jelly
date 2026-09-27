---
title: "River API — what we call and how"
purpose: "Working notes for #2 and #3. Facts marked SDK were verified by reading the installed river-client 0.12.0. Results from the live check land in docs/river-check.json."
updated: "2026-09-27"
---

# River API

## Setup

1. At **console.river.ai**, create an account and a **team**, then create a **team** API key on the API Keys page. Deployments need a team key; a personal key can't create them.
2. Put it in `.env` at the repo root (gitignored): `RIVER_API_KEY=rv_...`
3. Run the check (no install step; `uv` fetches the SDK):

```sh
uv run -p 3.12 --with river-client scripts/river_check.py
```

It calls `get_capabilities()`, picks a base model (Qwen3.6-35B-A3B first, then Qwen3.5-9B; override with `RIVER_BASE_MODEL`), makes one `chat_complete` call, and writes everything to `docs/river-check.json`. A bad key prints `River: Authentication failed…` and exits 1.

## What the SDK actually does (SDK)

Read from the installed package, because a few details differ from the docs:

| Thing | Reality |
|---|---|
| Package | `pip install river-client`, import `river_client`. Requires Python 3.12+ (`Requires-Python: >=3.12`); it won't install on the macOS system Python 3.9 |
| Auth | `river_client.Client(api_key=...)`. The key must be passed; the client does **not** read `RIVER_API_KEY` itself. Talks gRPC to `api.river.ai:443` |
| Models | `client.get_capabilities() -> list[str]` |
| Inference | `client.chat_complete(messages, base_model=...)` and `client.chat_complete_from_checkpoint(messages, checkpoint_path=...)`. Both return `ChatCompleteResult(response_json, status_code)` |
| Training session | `with client.session() as session:` then `session.create_model(base_model, lora=LoraConfig(rank=...))`. `LoraConfig` defaults to rank 16 |
| Training step | `model.train_step(data, lr, loss_fn="cross_entropy", grad_clip_norm=...)` returns `(ForwardResult, OptimStepResult)` |
| Training record | `river_client.renderers.get_renderer(base_model).build_training_example(messages, tools=..., train_on=TrainOnWhat.ALL_ASSISTANT).to_dict()` gives `{input_ids, attention_mask, weights}` with weights already left-shifted and normalized. The docs' `target_tokens` shape is not what the SDK sends |
| Tool calls | Renderers take OpenAI-style `tool_calls` on assistant messages and `ToolSpec {name, description, parameters}` |
| Checkpoints | `model.save_weights(name, mode="inference")` returns a `Checkpoint` |
| Serving | `client.create_deployment(checkpoint, unified_replicas=1, wait=True)` returns a `Deployment`. Gated: River has to enable it for the team |
| Data attestation | Optional `client.attest_training_data(...)` hashes the training data; passing it to `create_model` makes the server refuse to train if the manifest changes. Worth a line in the privacy pitch if time allows |
| Errors | `AuthenticationError`, `CapacityError`, `ModelNotFoundError`, `RiverConnectionError`, `RiverTimeoutError`, all `RiverError` |

## Message to post on River's Discord (tonight)

Copy and paste, filling in the team name:

> Hi River team! We're building at the Own Your Intelligence hackathon tomorrow. Our project trains a small model on an agent's own test-verified coding sessions (the test's exit code is the label) and routes that task type to it, with the frontier model as fallback.
>
> A few questions that decide our build:
> 1. Could you enable **deployments** for our team `<TEAM NAME>` on **Qwen3.6-35B-A3B** (or whichever small model you'd recommend)?
> 2. Does the deployment's OpenAI-compatible `chat/completions` endpoint support **`tools` / function calling**?
> 3. Rough wall-clock for LoRA SFT on ~50–100 short chat examples on that model?
> 4. Are there hackathon credits, and is there anything different about hackathon keys (rate limits, model access)?
>
> Thanks!

## Deployments status

Not asked yet. When you post, record the time here, and later the answer.

## Results

Filled in by `scripts/river_check.py` into `docs/river-check.json` once the key is in `.env`.
