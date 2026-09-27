---
title: "Research: Superset, QM and UFO"
purpose: "Primary-source research done 2026-09-26 to check the plan's assumptions. Facts carry source URLs; UNCONFIRMED marks what could not be verified."
updated: "2026-09-26"
---

# Research: Superset, QM, UFO (as of 2026-09-26)

Sources: I cloned `superset-sh/superset` and `yc-software/qm` (depth 1) and read the docs source (`apps/docs/content/docs/*.mdx`) and the code. I checked the live docs.superset.sh CLI page against the repo copy and they match. For UFO I read https://ufo.ai, https://ufo.ai/docs/*, and the install script, which I downloaded and did not run.

## Superset

**License and install.** It is Elastic License 2.0, not OSI open source (`LICENSE.md`). You can get it three ways:
- Desktop app: a macOS dmg. Linux AppImage is experimental and there is no Windows build.
- CLI: `curl -fsSL https://superset.sh/cli/install.sh | sh`
- Homebrew: `brew install superset-sh/tap/superset`

The desktop app installs a shim at `~/.superset/bin/superset`. The CLI is labelled **Beta** and the SDK **early alpha** (https://docs.superset.sh/cli/getting-started).

**CLI.** Source: https://docs.superset.sh/cli/cli-reference.
- **There are no `new`, `ls` or `connect` commands.** The real command groups are: `scripts, auth, start, stop, status, update, organization, projects, hosts, workspaces (ws), agents, terminals, browser, pages, mcp, tasks, automations, settings`.
- Global flags: `--json`, `--quiet`, `--api-key` (or the `SUPERSET_API_KEY` env var). When it detects an agent or CI (`CLAUDECODE`, `CI`, etc.) it defaults to JSON output.
- Sign-in is required: `superset auth login`, or `--api-key sk_live_…`.
- `superset start --daemon` runs the local host server (loopback only). `superset status` reports on it.
- Register a repo with `superset projects create --name X --local --import <path>` (or `--clone <url> --parent-dir`).
- `superset workspaces create` flags:
  - required: `--project <id>` and `--name`, plus `--local` or `--host`
  - `--branch`, `--base-branch`, `--checkout <local|worktree>`
  - `--agent <preset|uuid|superset>` and `--prompt`
  - `--model`, `--effort`, `--command`, `--tag` (repeatable)
  - it returns `{workspace, alreadyExists}`
- To start and read agents:
  - `agents create --workspace --agent --prompt [--model --effort]` returns `{kind, sessionId}`.
  - `agents read --workspace --terminal <sessionId> --local` returns the saved transcript.
  - `terminals read --max-lines`, `terminals send --text` and `terminals close` also exist.
- `automations list|get|create --rrule …|update|run|logs|pause|resume|delete|prompt get/set`.

**Spawning many agents.** The race-agents recipe gives this loop verbatim (https://docs.superset.sh/recipes/race-agents):
```bash
for agent in claude codex opencode; do
  superset workspaces create --project <projectId> \
    --name "race-$agent" --branch "race/$agent" --local \
    --agent "$agent" --prompt "$(cat prompt.md)"
done
```
To collect results, capture `--json`, then use `agents read` / `terminals read` for output and `workspaces get --field worktreePath` to diff each worktree. There is no documented "wait until done" call. Completion shows up only as UI status, chimes and hooks (UNCONFIRMED via CLI).

**SDK (`@superset_sh/sdk`).** It reads `SUPERSET_API_KEY` and `SUPERSET_ORGANIZATION_ID` (https://docs.superset.sh/sdk/reference). Methods: `tasks.*`, `workspaces.list/create/update/delete`, `projects.list`, `hosts.list`, `agents.list/create`, `terminals.create`, `automations.*`, `organization.members.list`. `workspaces.create` takes an `agents: [{agent, model?, effort?, prompt}]` array and returns a per-agent `{ok, kind, sessionId}`. It goes through the cloud relay, so the host must be online.

**MCP.** The server is at `https://api.superset.sh/mcp` (HTTP, OAuth or API key); add it with `claude mcp add superset --transport http https://api.superset.sh/mcp`. Tools include `workspaces_create` (with agent launches), `agents_create`, `terminals_create/send/read/close/list`, `automations_*`, `hosts_list`, `projects_list` and `pages_*` (https://docs.superset.sh/mcp-server).

**Per-agent config and a custom base URL.**
- The providers page says terminal agents "automatically just work". You set env vars "in your shell profile or per workspace via **Settings > Env**" (https://docs.superset.sh/providers). The documented examples are `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_API_KEY=` for OpenRouter and Vercel.
- In the code, each host agent row (`HostAgentConfig`) stores `command`, `args` and `env` (`packages/host-service/src/trpc/router/settings/agent-configs.ts`).
- In the desktop custom-agent form, leading `VAR=value` tokens in the command are parsed into `env` (`apps/desktop/src/renderer/lib/argv.ts`, `parseLaunchCommandString`). `agents create --agent <uuid>` then launches that row.
- **So the path is:** create a custom agent under Settings → Agents with a command like `ANTHROPIC_BASE_URL=http://localhost:4141 claude`. This is inferred from code and not tested.
- The CLI has no command to add or edit agent rows (`agents` only has list, create and read).
- Per-*workspace* env through the CLI is UNCONFIRMED.
- `--model` only accepts ids the host knows, such as `sonnet`, `opus` or `claude-opus-5-5`: "The host rejects an unknown id".

**Token and cost data.** The desktop Usage page estimates cost from local Claude Code / Codex session logs at API list rates. It breaks down by model and by workspace, and it only covers the local machine (https://docs.superset.sh/usage). **No CLI, SDK or MCP endpoint for usage is documented.**

**Worktree setup hooks.** `.superset/config.json` takes `{"setup": [...], "teardown": [...], "run": [...]}`, and setup runs on every workspace create. The env vars available are `SUPERSET_ROOT_PATH`, `SUPERSET_WORKSPACE_NAME` and `SUPERSET_WORKSPACE_PATH`. You can override without touching the repo via `~/.superset/projects/<repo-path>/config.json` or `.superset/config.local.json` (with `before` / `after`), or skip setup with `{"setup": []}`.

By default the agent starts **in parallel with setup**. The experimental setting "Wait for workspace setup before starting agents" chains them instead (https://docs.superset.sh/setup-teardown-scripts). To avoid 10 installs, a setup step like `ln -s "$SUPERSET_ROOT_PATH/node_modules" .` would work with this mechanism, but that is my suggestion, not something documented.

## QM (Quartermaster)

**Stack.** TypeScript run directly on Node, Fastify, Postgres, a Lit/Vite web UI, and an optional Slack plugin (Bolt). MIT license. The default harness is `HARNESS=pi` (`@earendil-works/pi-ai` 0.82.0 plus a forked `pi-coding-agent`). Other harnesses are OpenCode, Codex and Claude Code (README).

**How agents are configured.** Env vars (`.env.example`, "every knob, documented in place") plus the admin panel. For deployments, a deployment directory with `qm.config.jsonc`, validated by the `qm` CLI.

**Model provider config.** There are three ways to point it at a model:

1. **Base-URL overrides for the built-in providers.** In `src/model/provider-endpoints.ts`:
   ```ts
   const PROVIDER_BASE_URL_ENV = { anthropic: "ANTHROPIC_BASE_URL", openai: "OPENAI_BASE_URL", openrouter: "OPENROUTER_BASE_URL" };
   ```
   `parseProviderBaseUrl` accepts plain `http:`, rejects credentials, query strings and fragments, and has no localhost block. `src/config.ts:1404-1405` passes `OPENAI_BASE_URL` to the Codex child process and `ANTHROPIC_BASE_URL` to the Claude child process.
2. **Custom providers, the best fit for us.** In `src/model/custom-providers.ts`, protocols are `"openai"`, `"openai-responses"` and `"anthropic"`, mapping to `openai-completions`, `openai-responses` and `anthropic-messages`. You register one through the admin UI (`plugins/admin/ui/settings-providers.ts`) or with `PUT /v1/admin/custom-providers/:provider`, body `{name, protocol, baseUrl, models:[{id, contextWindow?, maxTokens?, input?, output?}], apiKey?, validate?}`.
   - Key validation calls `GET ${baseUrl}/models` for the openai protocol. So `baseUrl` should likely be `http://localhost:4141/v1` (inferred). Pass `"validate": false` if the proxy has no `/models`.
   - Custom models are "gated to harnesses that route through pi-ai", so only the Pi harness can use them.
3. **Model gateway.** `MODEL_GATEWAY_URL`, `MODEL_GATEWAY_API_KEY`, `MODEL_GATEWAY_API_KEY_HEADER` and optional `MODEL_GATEWAY_MODELS` (`docs/model-gateway.md`). Discovery needs `GET /v1/models` **and** LiteLLM's `GET /model_group/info` with pricing and tool-support metadata. Protocol is chosen by provider metadata: Anthropic-only groups use `/v1/messages`, OpenAI/Azure use `/v1/responses`, and anything else uses chat completions.

**APIs called.** All three are possible, depending on the model's `api`: chat completions, Responses, and Anthropic Messages. Which API the built-in `openai` models use under `OPENAI_BASE_URL` is UNCONFIRMED; the code suggests `openai-responses`.

**Running it locally.**
- `npm ci`, then `npm run dev-instance:web`. That script runs `scripts/dev/cli.ts`, which starts Postgres with `docker run` (`scripts/dev/lib/postgres.ts`).
- The local sandbox needs Docker plus `npm run sandbox:local:build`.
- Or run `npm run dev` / `npm start` against a `.env`. Without `DATABASE_URL`, sessions live only in memory.
- `.env.example` has signing secrets that must be filled in, and the minimum set for a working run is UNCONFIRMED.

## UFO (ufo.ai)

- It is a hosted, chat-first "AI teammate" from Metalcraft, Inc., with a browser, terminal, connectors (GitHub, Slack, Google Drive, Gmail, Linear and more), memory and scheduled tasks (https://ufo.ai/docs/getting-started/introduction).
- The Sept 10, 2026 changelog lists: pick a Claude, GPT or GLM model per chat; use a ChatGPT subscription; the terminal client `curl -fsSL https://ufo.ai/ufo | sh` (https://ufo.ai/docs/changelog/).
- **Billing:** a prepaid balance. "A workspace can enter its own model provider key", with no base URL mentioned (https://ufo.ai/docs/workspace/billing/).
- **Install script** (2567 bytes, `/bin/sh`):
  - picks a target such as `aarch64-apple-darwin` or `x86_64-unknown-linux-musl`
  - downloads `$UFO_URL/ufo/bin/$TARGET` to `$UFO_HOME/bin/ufo` (default `~/.ufo`)
  - symlinks it into `~/.local/bin` if that is on PATH, otherwise appends a PATH line to your shell rc
  - then runs `exec "$BIN" "$@"`
- **No API, SDK, custom-endpoint or self-host option is documented.**

## Plan-changing facts

1. **Superset `--model` will not route to our proxy.** The host rejects unknown ids. To route through localhost:4141, set `ANTHROPIC_BASE_URL` (or the OpenAI equivalent) in the agent's env: either a custom agent row whose command starts with `VAR=value`, or Settings > Env. Both are desktop-UI steps; the CLI cannot create agent rows.
2. **Superset has no usage or cost API and no "wait until done" call.** Our proxy must be the source of truth for tokens, cost and completion. Poll with `agents read` / `terminals read` and diff each worktree yourself.
3. **Superset setup runs in parallel with the agent by default.** Turn on the experimental "wait for setup" setting, and use `.superset/config.local.json` to link dependencies instead of reinstalling. Superset also needs a signed-in account and the `superset start` host daemon.
4. **QM supports our proxy natively, but only with the Pi harness.** Register a custom provider with protocol `"openai"` (chat completions) and `baseUrl` `http://localhost:4141/v1`, with `validate:false` if the proxy has no `/models`. The gateway route needs LiteLLM's `/model_group/info`, so skip it. The local QM dev instance needs Docker (Postgres and the sandbox).
5. **UFO gives us nothing we can wire in.** It is a closed, hosted product with no base-URL or API docs. Drop it or treat it as a demo only.

Sources also used: https://aiagentstore.ai/ai-agent/ufo and https://github.com/slavakurilyak/awesome-ai-agents/pull/372 came up in search. The PR describes a "UFO by ALIENZ" team-chat product, and I did not confirm it is the same thing as ufo.ai.
