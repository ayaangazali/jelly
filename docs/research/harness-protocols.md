---
title: "Research: Agent harness wire protocols"
purpose: "Primary-source research done 2026-09-26 to check the plan's assumptions. Facts carry source URLs; UNCONFIRMED marks what could not be verified."
updated: "2026-09-26"
---

**Verdict: the "one env var" claim is false.** Of the four harnesses I checked, none reads `OPENAI_BASE_URL` for model traffic, and the two biggest (Claude Code and Codex) don't speak Chat Completions at all.

## 1. Claude Code

- **Protocol:** Anthropic Messages. A gateway must serve `/v1/messages`; `/v1/messages/count_tokens` is optional, and without it Claude Code estimates tokens from character counts. The gateway must forward the `anthropic-beta` and `anthropic-version` headers unchanged. Inference requests arrive as `POST /v1/messages?beta=true`, and there is a `HEAD /api/hello` warm-up probe you can reject. https://code.claude.com/docs/en/llm-gateway-protocol
- **Endpoint env var:** `ANTHROPIC_BASE_URL`. Credentials go in `ANTHROPIC_AUTH_TOKEN` (sent as `Bearer`) or `ANTHROPIC_API_KEY` (sent as `X-Api-Key`). https://code.claude.com/docs/en/env-vars
- **Model env vars:**
  - `ANTHROPIC_MODEL`
  - `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` (the Haiku one is "also used for background functionality"), `ANTHROPIC_DEFAULT_FABLE_MODEL`
  - `ANTHROPIC_DEFAULT_MODEL` (v2.1.236 or later)
  - `CLAUDE_CODE_SUBAGENT_MODEL`
  - `ANTHROPIC_SMALL_FAST_MODEL` is marked **[DEPRECATED]**.
  - Source: same env-vars page.
- **`OPENAI_BASE_URL`:** it is not in the env-vars reference (I grepped the raw page for `OPENAI_*` and found nothing). Claude Code does not honour it.
- **Non-Claude models:** Anthropic "doesn't support routing Claude Code to non-Claude models through any gateway." It works in practice through translators, but it is unsupported. https://code.claude.com/docs/en/llm-gateway
- **Streaming requirements:**
  - Don't buffer the response, or Claude Code stalls.
  - Relay every event through `message_delta` and `message_stop`, without dropping, duplicating or reordering.
  - Forward `ping` events. Claude Code aborts a stream that is silent for 300 seconds.
  - Return `content-type: text/event-stream`.
  - Forward error bodies unmodified, because Claude Code's retry logic matches on the upstream's error wording.
  - Source: the llm-gateway-protocol page.
- **Unrecognised model IDs** (for example a gateway alias for your small model): Claude Code assumes a current Claude model. It sends `thinking: {"type":"adaptive"}`, effort and context-management fields, and assumes a 200K context window. A non-Anthropic backend has to strip or translate those fields. Same page.

## 2. OpenAI Codex CLI

- **Responses API only.** The config reference says `wire_api`: "responses is the only supported value." https://learn.chatgpt.com/docs/config-file/config-reference
- In the source, `wire_api = "chat"` is now a hard error ("`wire_api = \"chat\"` is no longer supported", `codex-rs/model-provider-info/src/lib.rs`). It was deprecated on 2025-12-09, and a maintainer set removal for 2026-02-01. https://github.com/openai/codex/discussions/7782
- **Custom provider config** in `config.toml`: `model_provider = "proxy"`, then a `[model_providers.proxy]` table with `base_url` and `env_key`, plus optional `http_headers`, `env_http_headers` and `query_params`. To point the built-in OpenAI provider elsewhere, use the config key `openai_base_url`. https://learn.chatgpt.com/docs/config-file/config-advanced
- **`OPENAI_BASE_URL`:** in current `codex-rs` main, the only non-test reference is in the network-proxy credential broker. It is not a provider base-URL override. There is also a `CODEX_OSS_BASE_URL` env var for `--oss`. So for Codex's model endpoint it effectively does not work (my own grep of the source; the docs don't discuss it).
- **Consequence:** a proxy that only exposes `/v1/chat/completions` cannot serve Codex. You need `/v1/responses`.

## 3. Other harnesses

- **OpenCode:** configured in `opencode.json`, not an env var: `provider.<id>` with `"npm": "@ai-sdk/openai-compatible"` (for `/v1/chat/completions`) or `@ai-sdk/openai` (for `/v1/responses`), plus `options.baseURL` and a `models` map. https://opencode.ai/docs/providers/
- **Aider:** `OPENAI_API_BASE` (not `OPENAI_BASE_URL`) plus `OPENAI_API_KEY`, and the model is passed as `--model openai/<name>`. https://aider.chat/docs/llms/openai-compat.html

## 4. Translation layers

- **LiteLLM proxy:** `/v1/messages` works with "All LiteLLM supported providers" (openai, bedrock, vertex_ai, gemini, azure and others), with streaming. Responses carry `cache_creation_input_tokens` and `cache_read_input_tokens`. The docs also have a separate section on native `/v1/messages` and `/v1/responses` passthrough for OpenAI-compatible providers. https://docs.litellm.ai/docs/anthropic_unified
- The Claude Code tutorial takes 5 steps: write `config.yaml`, run `litellm --config`, test with curl, set `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`, run Claude Code. https://docs.litellm.ai/docs/tutorials/claude_responses_api
- Whether LiteLLM forwards `cache_control` to non-Anthropic backends is **UNCONFIRMED** (not stated on the pages I read).
- **claude-code-router:** a local gateway on `127.0.0.1:3456` for Claude Code, Codex, Kimi CLI and others. Install with `npm i -g @musistudio/claude-code-router`. About 37.4k stars, 949 open issues, version 3.1.0, MIT licence. https://github.com/musistudio/claude-code-router
- **codex-proxy:** a community Responses-to-Chat bridge mentioned in discussion #7782. I did not check its maturity.

## 5. Pitfalls

- **Streaming formats differ.**
  - Anthropic sends named events: `message_start`, `content_block_start`, `content_block_delta` (subtypes `text_delta`, `input_json_delta` carrying `partial_json` for tool arguments, `thinking_delta`), `content_block_stop`, `message_delta`, `message_stop`, `ping`, `error`. The usage figures in `message_delta` are cumulative. https://platform.claude.com/docs/en/build-with-claude/streaming
  - OpenAI Chat sends `chat.completion.chunk` objects: text and tool calls arrive in `choices[].delta` (tool calls carry index, id and argument fragments), and `finish_reason` is one of `stop`, `length`, `tool_calls`, `content_filter`. Streamed usage only appears in the final chunk if the request sets `stream_options.include_usage: true`. https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events
- **Caching:**
  - Anthropic uses `cache_control` markers, either one at the top level of the request or on individual blocks. Claude Code puts them on `system` blocks and on message entries. If a proxy drops them, nothing errors: every turn is just billed as uncached input. Converting block-form `system` or message content into plain strings also defeats caching. Sources: llm-gateway-protocol page and https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - OpenAI caching is automatic, with an optional `prompt_cache_key`. https://developers.openai.com/api/docs/guides/prompt-caching
- **Where cached tokens are reported:**

| Provider / API | Cached-token fields | Notes |
|---|---|---|
| Anthropic Messages | `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens` | `input_tokens` excludes both, so total input = read + creation + `input_tokens` |
| OpenAI Chat Completions | `usage.prompt_tokens_details.cached_tokens` (and `cache_write_tokens`) | |
| OpenAI Responses | `usage.input_tokens_details.cached_tokens` (and `cache_write_tokens`) | |

  Sources: the Anthropic caching page, the OpenAI caching guide, and the Chat Completions API reference (via search results).
- **Attribution block:** Claude Code prepends an attribution block to `system`. Reordering the array or merging it into a string breaks both prompt caching and the positional strip. Set `CLAUDE_CODE_ATTRIBUTION_HEADER=0` if the gateway reshapes the system prompt. llm-gateway-protocol page.

## 6. Turns and session grouping

- **Claude Code headers** (from the llm-gateway-protocol page):
  - `x-claude-code-session-id` on every request, "to aggregate all requests from one session".
  - `x-claude-code-agent-id` and `x-claude-code-parent-agent-id` on subagent requests.
  - Hint headers, off by default behind a custom base URL until you set `CLAUDE_CODE_GATEWAY_HINT_HEADERS=1` (v2.1.273 or later):
    - `x-claude-code-request-class` (`main`, `subagent`, `workflow`, `compaction`, `auxiliary`)
    - `x-claude-code-prompt-id` (one UUID per user prompt, v2.1.283 or later)
    - `x-claude-code-prev-tool-durations`
- **Codex headers** (source only, not in the docs):
  - `session-id` and `thread-id` (`codex-rs/codex-api/src/requests/headers.rs`)
  - `x-client-request-id` set to the thread id
  - `x-openai-subagent` on subagent requests (`codex-rs/codex-api/src/endpoint/responses.rs`)
- **`metadata.user_id`** is documented only as an opaque end-user identifier (https://platform.claude.com/docs/en/api/messages). That Claude Code puts a session id inside it is **UNCONFIRMED**. Use the header instead.
- **What a "turn" is:** no source defines "turn = one model request." Proposed metric: turns per task = the number of requests where `x-claude-code-request-class=main`, grouped by `x-claude-code-prompt-id`, excluding `auxiliary` and `compaction`. Without the hint headers you'd have to count every request per session id, which inflates the number with title and classifier calls.

## Design recommendation

Minimum change: **pick Claude Code as the single demo harness** and add `POST /v1/messages` to the proxy.
- **Frontier route:** pass the request through to Anthropic byte-for-byte.
- **Small-model route:** translate Messages to Chat Completions, which LiteLLM can do rather than hand-writing it.
- **Keep the existing endpoint:** `/v1/chat/completions` stays for OpenCode and Aider.
- **Codex:** it would need a third endpoint, `/v1/responses`. Leave it out of the demo.
- **Demo env:**
  - `ANTHROPIC_BASE_URL=http://localhost:4141` and `ANTHROPIC_AUTH_TOKEN=<anything>`
  - `CLAUDE_CODE_GATEWAY_HINT_HEADERS=1`, for turn counting
  - `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`, which stops the pre-release beta fields; the adaptive `thinking` field isn't covered by it, so the small-model translation still has to drop it
- **Test before the demo:** streaming without buffering, `ping` forwarding, and `cache_control` passthrough on the Anthropic route.

**Honest version of the claim:** "One base-URL setting per harness, and the variable differs: `ANTHROPIC_BASE_URL` for Claude Code, `openai_base_url` or a `model_providers` entry in `config.toml` for Codex (Responses API only), `baseURL` in `opencode.json` for OpenCode, `OPENAI_API_BASE` for Aider. Claude Code needs an Anthropic Messages endpoint and Codex needs a Responses endpoint, so the proxy has to speak more than Chat Completions." Also note that Anthropic officially doesn't support pointing Claude Code at non-Claude models.
