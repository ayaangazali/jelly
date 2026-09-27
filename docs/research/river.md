---
title: "Research: River AI"
purpose: "Primary-source research done 2026-09-26 to check the plan's assumptions. Facts carry source URLs; UNCONFIRMED marks what could not be verified."
updated: "2026-09-26"
---

## River AI research report (read on 2026-09-26)

I pulled the raw markdown for every docs page with `curl https://docs.river.ai/<page>.md` and got 21 pages, all HTTP 200: the index, quickstart, api-basics, models, all SFT pages, all RL pages, distillation, requests, checkpoints, deployments, operations, losses and the full Python API reference. I also read the river.ai homepage, /changelog, /blog and /support.

Things I could not get:
- https://river.ai/pricing returns 404. The pricing table is on the homepage instead.
- There is no GitHub org: `api.github.com/orgs/river-ai` returns 404, and neither the site nor PyPI links to one.
- console.river.ai returns 200 but needs a login, so I could not read it.

**The main correction to our plan:** River has no upload-a-JSONL "fine-tune job" API. It is a set of training primitives driven from our own Python process: create a LoRA model, then call `forward_backward`, `optim_step` and `sample` ourselves.

### 1. Auth
- You create an API key on the Console's **API Keys** page and set `RIVER_API_KEY="rv_..."`. Source: https://docs.river.ai/quickstart/
- You pass it as `river.Client(api_key=...)`. The client talks **gRPC** to `api.river.ai:443` over SSL, not plain HTTP. Source: https://docs.river.ai/python-api/
- For the OpenAI-compatible deployment endpoint, the key goes in as `OpenAI(api_key=RIVER_API_KEY, base_url=deployment.base_url)`. Source: https://docs.river.ai/guides/deployments/
- **UNCONFIRMED:** the HTTP header name. River never states it. It is probably `Authorization: Bearer`, because that is what the OpenAI SDK sends.
- Deployments require a **team** API key. Personal keys cannot create deployments. Source: https://docs.river.ai/guides/deployments/

### 2. Inference
- **Training-side sampling (Python/gRPC):**
  - `client.sample(prompt, base_model=...)`, `model.sample(...)`, and `session.sample(..., checkpoint=ckpt)`. Source: https://docs.river.ai/guides/requests/
  - `client.chat_complete(messages, base_model=)`, `client.chat_complete_from_checkpoint(messages, checkpoint_path=)` and `client.chat_complete_from_training(messages, model_id=)`. These take OpenAI-format messages and return `response_json` plus `status_code`. Source: https://docs.river.ai/python-api/
- **OpenAI-compatible HTTP:** only through a dedicated deployment. Source: https://docs.river.ai/guides/deployments/
  - `deployment.base_url` "already includes the OpenAI API prefix".
  - `chat.completions.create(..., stream=True)` is shown working, so SSE streaming is supported.
  - `/responses` works only in stateless form: `store=False` is required, and `previous_response_id` and background processing are unsupported.
  - `model=deployment.model`, which equals the deployment id and "also accepted by global /v1". Source: https://docs.river.ai/python-api/
  - **UNCONFIRMED:** the global base URL path.
- **Tool/function calling on the serving endpoint:** UNCONFIRMED. Tools are documented only inside RL environments (`@rl.tool`), where River says the renderer handles "reasoning and tool tokens". Source: https://docs.river.ai/guides/rl-tools/
- **Models** (source: https://docs.river.ai/guides/models/, context windows from the homepage catalog):
  - Qwen3.5-9B, Qwen3.6-35B-A3B-FP8, Qwen3.8-27B-FP8, Qwen3.5-122B-A10B-FP8, Qwen3.5-397B-A17B-FP8
  - Kimi-K2.6-NVFP4 (32k and 262K variants), GLM-5.2-NVFP4 (32k and 262K variants), GLM-5.3-Flash
  - DeepSeek-V4-Flash-0731, Nemotron-3.5-Lightning-30B-A3B
  - Everything not listed with a 32k variant has a 262k context.
  - Access is granted per account. `client.get_capabilities()` returns the authoritative list for a key.
- The Qwen models are reasoning models and emit `<think>` blocks. Source: https://docs.river.ai/guides/requests/

### 3. Fine-tuning (LoRA SFT)
- **There is no job endpoint and no dataset upload.** You tokenize locally with a HuggingFace tokenizer and send batches of `{"input_ids", "target_tokens", "weights"}`. Source: https://docs.river.ai/guides/sft/
  ```python
  {"input_ids": prompt_ids+completion_ids, "target_tokens": ids[1:]+[EOS],
   "weights": [0.0]*(len(prompt_ids)-1) + [1.0]*(len(completion_ids)+1)}
  ```
- **Training loop:** `session.create_model(base_model, lora=river.LoraConfig(rank=32))`, then `forward_backward(batch, loss_fn="cross_entropy")` and `optim_step(lr=2e-4, grad_clip_norm=1.0)` (AdamW). `train_step(batch, loss_fn, lr)` combines the two. Source: https://docs.river.ai/guides/sft/
- **Training is LoRA-only.** Source: https://docs.river.ai/python-api/
- **LoRA settings:** `rank` 1–32 by default, plus `train_attn`, `train_mlp`, `train_unembed` and `seed`. Source: https://docs.river.ai/guides/lora/
- **Dataset size:** no minimum or maximum is documented. The only limit is a 1 GiB per-request upload, and larger requests are split. Source: https://docs.river.ai/python-api/
- **Statuses:** none for training, because the loop runs synchronously in our process.
- **Getting a model id back:**
  - `model.model_id` looks like `<session>:model:1`.
  - `model.save_weights(name, mode="inference")` returns a path like `river://<run>/sampler_weights/<name>`.
  - `mode="training"` also keeps the optimizer state so training can resume.
  - Checkpoints expire after 1 year by default, which is also the maximum.
  - Sources: https://docs.river.ai/guides/checkpoints/ and https://docs.river.ai/python-api/
- **Wall-clock time:** no figure is given. The toy example gets from loss 34 to 0 in about 15 steps. **UNCONFIRMED** for real data.
- Weights can be downloaded from Console > Checkpoints as a PEFT LoRA adapter. Source: https://docs.river.ai/guides/operations/

### 4. RL
- You write an `rl.Env` subclass with `reset(row)`, which returns messages, and `async reward(traj, row)`, which returns a float. **The reward code and tools run in our Python process**, not on River's side. Source: https://docs.river.ai/guides/rl-tools/
- Your program samples attempts and scores them before building the update; River does not decide the reward. Source: https://docs.river.ai/guides/api-basics/
- **Recipe objects:** `rl.RolloutEngine(model, env, renderer, budget=rl.Budget(...), schedule=rl.Schedule(concurrency=64))`, then `rl.AsyncTrainer(optimizer=rl.Adam(lr=1e-5), advantage=rl.GroupCentered(), loss="cispo", groups_per_step=8, group_size=8, max_staleness=0)`, then `rl.run(trainer, rows, steps=20)`. Source: https://docs.river.ai/guides/rl-sync/
- Multi-turn tool use comes from `tools = [...]` plus `max_turns`. Source: https://docs.river.ai/guides/rl-tools/
- **Duration:** not documented. **UNCONFIRMED.**

### 5. Serving a fine-tuned model
- **Setup:** `client.create_deployment(checkpoint="river://...", unified_replicas=1, idempotency_key=..., wait=True)`.
- **Gating:** this is a gated feature, off by default. You have to "Contact River to enable" it per team and per base model.
- **Cold start:** no figure. The default `wait_timeout` is 1800 s.
- **Phases:** `accepted`, `provisioning`, `ready`, `degraded`, `unavailable`, `scaled_to_zero`, `failed`, `deleting`, `deleted`.
- **Billing:** by "requested GPU-hours" from acceptance until scale-to-zero or delete. **UNCONFIRMED:** the GPU-hour rate.
- Sources: https://docs.river.ai/guides/deployments/ and https://docs.river.ai/python-api/
- **Fallback that needs no deployment:** `client.chat_complete_from_checkpoint`, which is per-token. Our proxy could call it through gRPC.

### 6. Pricing, rate limits, credits
All prices are homepage "Preview rates, subject to change", USD per 1M tokens (https://river.ai/):

| Model | Prompt | Completion | Training |
|---|---|---|---|
| Qwen3.5-9B | $0.66 | $1.99 | $1.46 |
| Qwen3.6-35B-A3B | $0.33 | $0.82 | $1.00 |
| Nemotron-30B | $0.30 | $0.80 | $1.00 |
| Qwen3.8-27B | $1.80 | $5.50 | $4.10 |

- Cached prompt tokens cost 20% of the prompt rate.
- Checkpoint storage is $0.10/GB/month.
- **Rate limits:** none published. The docs mention only an autoscaling pool and a `CapacityError`. **UNCONFIRMED.** Sources: https://docs.river.ai/guides/operations/ and https://docs.river.ai/python-api/
- **Credits:** Igor Babuschkin posted that River is co-hosting the "Own Your Intelligence Hackathon" with YC and "will give out free credits for our training API at the event". Source: https://x.com/ibab/status/2096404566975946901 (seen only as a search snippet). **UNCONFIRMED** that this is our event.

### 7. SDKs
- **Python:** `pip install river-client`, imported as `river_client`. The latest version is 0.12.0 (https://pypi.org/pypi/river-client/json).
- **JS SDK and CLI:** none documented. **UNCONFIRMED.**
- The homepage has runnable examples, including `rl_loop.py` (GRPO on Kimi).
- Support is via Discord or support@river.ai, with a stated response time of up to 2 business days (https://river.ai/support).

### 8. Can we train live in 3h45m?
**Helps:**
- No queue or job wait: training runs in a live session and we can sample the trained weights right away.
- Toy SFT converges in about 15 steps.
- Cheap models are available (Qwen3.6-35B-A3B is $1.00 per 1M training tokens).

**Hurts:**
- Deployments are gated and need a team key plus manual enablement by River.
- The OpenAI endpoint exists only on deployments.
- Model access is per account.
- We must write our own tokenization and loss masking, or use the renderers.
- No throughput or duration numbers are published.

## Plan-changing facts
1. **There is no JSONL upload or job API.** SFT is our own Python loop: we tokenize and mask the data and call `forward_backward`/`optim_step`. The dataset converter has to emit `input_ids`/`target_tokens`/`weights` using the base model's tokenizer.
2. **The OpenAI-compatible endpoint (chat/completions with streaming, stateless /responses) exists only on dedicated deployments.** These are gated, need a team key and must be enabled by River. We should ask River before the event. The fallback is `chat_complete_from_checkpoint` over gRPC behind our proxy.
3. **Reward code runs on our side** (`rl.Env.reward`, `@rl.tool`), so verified coding-agent runs can feed an RL environment directly. No duration numbers exist, so RL in the window is a gamble; SFT is the safe path.
4. **Our key may not see every model.** Run `client.get_capabilities()` first thing. Qwen3.6-35B-A3B is the cheapest for training and is the one the SFT guide uses; Qwen3.5-9B is the small model from the RL guide.
5. **Tool calling on the serving endpoint, the HTTP auth header, rate limits and the GPU-hour deployment price are all undocumented.** We should confirm them with River (Discord or api@river.ai) before building the proxy around them.
