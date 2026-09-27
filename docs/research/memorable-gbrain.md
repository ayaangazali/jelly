---
title: "Research: Memorable and GBrain"
purpose: "Primary-source research done 2026-09-26 to check the plan's assumptions. Facts carry source URLs; UNCONFIRMED marks what could not be verified."
updated: "2026-09-26"
---

I found enough to answer most questions, but several details are unconfirmed, mainly because the Memorable CLI is closed source (details at the end). All claims below come from pages I actually read.

# Memorable

**What it is:** `memorable-cli` v0.5.30 on npm (first published 2026-08-22, 38 versions). The license is a proprietary EULA that forbids reverse engineering and decompiling. There is no public repo: gbrain's docs say "closed source … no public repository" (https://github.com/garrytan/gbrain/blob/master/docs/memorable-agents.md). The npm tarball is one bundled `dist/cli.js`, and I did not decompile it.

## 1. CLI commands
Running `memorable` with no arguments groups them like this:
- **setup:** `init setup login install-hooks agents-md`
- **memory:** `record ingest backfill recall show list chain`
- **upkeep:** `prune enable disable forget flush`
- **inspect:** `status doctor eval notices`
- **integrate:** `mcp hook`
- Plus `start`.

What the docs say each does (https://www.memorable.sh/doc/cli, npm README):
- `login` signs in through a device flow; `login --paste` takes an `mk_` key on stdin. `init [gbrain|qm]` picks the backend. `enable` is write consent. `disable` makes memory read-only. `forget` denies everything, recall included.
- `ingest <trace.json | ->` stores a procedure from any harness's trace. `record [--session]` only works on the gbrain backend and turns the newest captured session into a procedure.
- `recall "<task>" [--single|--chain]` finds matches, e.g. `0.86 procedures/ab12cd34-fix-failing-order-tests [lexical]`. `show <slug>` prints one procedure with a guardrail wrapper.
- `list [--all] [--json]` shows slugs, the preferred revision, recall count and "how often the session went well afterwards".
- `chain "<task>" [--render] [--json]` builds an ordered plan from several procedures.
- `prune <slug>|--stale|--superseded [--dry-run]` deletes procedures.
- `status` and `doctor` check state; `setup` does init + enable + AGENTS.md in one step; `install-hooks [codex]` installs hooks.
- **JSON output:** confirmed only for `list --json` and `chain --json`.
- **UNCONFIRMED:** what `backfill`, `eval`, `flush`, `notices` and `hook` do (listed but not documented anywhere), and whether `show` has a JSON flag. There is no `export` command. `--help` on a subcommand just prints the main banner.

## 2. Procedure schema
The only documented shape is the draft returned by `/v1/extract` (https://www.memorable.sh/doc/api):
- `draft`: `title`, `session_id`, `schema_version` ("1.0.0"), `trigger_signature{entities, search_text}`, `preconditions`, `postconditions` (e.g. "final command exited successfully: …"), `embedding`, `embedding_model`
- `steps[]`: `seq`, `action`, `activity_class`, `command?`, `repeat_count`, `targets?`, `creates?`
- Chain output shows "needs:" (files read) and "verified by:" (the command).
- **Run count and outcomes** are not part of the procedure. They live in `~/.memorable/stats.json` on your machine, "never in the store" (npm README).
- **Failed runs:** traces that are empty or read-only are refused and logged to `~/.memorable/rejected.jsonl` with a reason. Failed tool calls can be sent (`result: {ok:false}` or `{exit_code}`). **UNCONFIRMED:** whether a failed session is ever stored as a procedure or can be retrieved.
- **UNCONFIRMED:** the exact fields in the local stored record.

## 3. POST /v1/extract
- **Host:** `https://memorable-extraction-api.memorable.workers.dev`
- **Auth:** `Authorization: Bearer mk_…`. Keys come from the device flow (`POST /v1/device/code` with `{hostname}`, then poll `/v1/device/token`) or from the dashboard. `POST /v1/keys` returns 403.
- **Body:** `{session_id, harness, task_description, skip_embedding?, tool_calls:[{name, input:{command|file_path|path|pattern|url|query}, result?:{ok}|{exit_code}}]}`. The CLI's `ingest` also accepts `workflow_id?` and `prompt?`.
- **Harness names:** `claude-code`, `codex` and `opencode` get curated tool registries. Any other string stores non-shell steps as `other`.
- **Limits:**
  - 300 requests/min and 5,000/day per key
  - 8 MB body, 2,000 tool calls, 2,000-character prompt
  - Free tier is 1,000 memorables/month plus a one-time reserve of 500
  - Once the allowance runs out it still returns 200, with `refused: "allowance_exhausted"`
- **Other endpoint:** `POST /v1/embed` with `{text}`.

## 4. MCP server
`memorable mcp` runs over stdio and is read-only. Its five tools are `memorable_recall`, `memorable_show`, `memorable_list`, `memorable_status` and `memorable_explain_recall`, each marked readOnlyHint. Setup: `claude mcp add memorable -- memorable mcp`. **UNCONFIRMED:** what each tool returns (https://www.memorable.sh/doc/cli).

## 5. Where the store lives
- **local (default):** `~/.memorable/procedures.jsonl`. Every line is **encrypted with AES-256-GCM**. The key is in the macOS Keychain, or `~/.memorable/store.key`, or `MEMORABLE_STORE_KEY` (npm README). You cannot parse the file directly; use `memorable list --json`.
- **gbrain:** your gbrain database (PGLite or Postgres), written through gbrain's `put_page`. Needs Bun (https://www.memorable.sh/doc/gbrain).
- **qm:** QM's own Postgres.
- **Service side:** the README and API page say the task line and steps are kept in Memorable's Postgres. The privacy page (https://www.memorable.sh/legal/privacy) says the opposite: "We keep no copy" and task descriptions are "written to no table". The docs contradict each other.
- **Raw Codex traces:** `memorable install-hooks codex` with **no account** writes `~/.memorable/traces/<session-id>/<turn-id>.json`. Each file holds the prompt, minimized tool inputs, tool outcomes and `agent_output`, but not command output or file contents.

## 6. Harnesses and hooks
- **Claude Code:** `install-hooks` adds a prompt hook that runs recall and edits `~/.claude/settings.json`.
- **Codex:** `install-hooks codex`. Codex does not save per-call success flags.
- **Cursor and others:** `setup` or `agents-md` writes instructions into AGENTS.md.
- **Through gbrain:** Claude Code and Codex sessions are captured at session end. OpenClaw captures tool names only, so the API rejects those traces (`no_decisive_steps`) (gbrain `memorable-agents.md`).

## 7. Privacy and consent
- Consent fails closed: unset means deny. Nothing is sent before `enable`.
- **What is sent:** tool names, 12 allow-listed argument fields and outcomes. Home directories become `~`; emails and credential-like strings are redacted. The task line is cut to 200 characters.
- **Through gbrain there are three switches:** `memorable enable`, gbrain's `integrations.memorable.enabled`, and a disclosure stamp. `GBRAIN_MEMORABLE=0` turns everything off.
- **Stale gbrain doc:** it says `init` issues an anonymous key. That contradicts the 403 on `/v1/keys` above.

## 8. Benchmarks
- **gstack** (https://www.memorable.sh/case-studies/gstack):
  - 15,593 → 293 tokens per prompt (−98%)
  - Turns 16 → 13 (−19%)
  - The page says both "454 runs, every one passed" and "125/125", which don't agree.
- **Quartermaster** (https://www.memorable.sh/case-studies/quartermaster):
  - Tool calls 5 → 3 (−40%)
  - Pass rate 80% → 91% over 150 pooled runs
  - Across five task families: 87% → 97%
- **OpenHome** (https://www.memorable.sh/case-studies/openhome):
  - Task completion 70% → 100%
  - Live demo 50% → 100% on 8 tasks
  - 0 wasted tool calls

# GBrain

There are two different things under this name:
- **gbrain.io** is a hosted team workspace.
- **github.com/garrytan/gbrain** is the MIT, TypeScript, self-hostable engine. It is at v0.59.0.0 with about 30.3k stars and was pushed 2026-09-26.

## 1. Reading and writing from an external process
- **Hosted:**
  - MCP at `https://gbrain.io/mcp`. `claude mcp add gbrain -t http https://gbrain.io/mcp`, or a token via `--header "Authorization: Bearer <token>"`.
  - Memory tools are `recall`, `remember`, `search`, `fetch` "and the rest" (https://gbrain.io/docs/tools/assistants).
  - The `gbrainio` CLI (`curl -sSL https://gbrainio.terminalwire.sh | bash`) only covers tools like Gmail, Drive and search. It has **no documented memory command** (https://gbrain.io/docs/tools).
- **Self-hosted:**
  - `gbrain put <slug>` with the content on stdin (confirmed in `src/core/ops/pages.ts`: `cliHints: { name: 'put', positional: ['slug'], stdin: 'content' }`)
  - `gbrain get <slug>`, `gbrain import <dir>`, `gbrain search … --json`
  - `gbrain remember "…" --provenance … --entity …`
  - MCP tools `put_page` and `get_page`

## 2. Memory format and UI
One markdown file per note, with frontmatter-style metadata (date, owner, status) and tags. Notes sit in folders shown in the **Memory** tree, and each note records its source and when it was written (https://gbrain.io/memory/features/plain-text-files, https://gbrain.io/docs/workspace/memory). Folders are made by the agent. An export gives a markdown tree with git history plus a Postgres dump (`pages`, `links`, `facts`, … tables) (https://gbrain.io/docs/workspace/export).

## 3. MCP, auth and permissions
- **Hosted:** OAuth sign-in or a bearer token. Memory access is **Read** (search/recall) or **Full** (remember/link/forget), set per client. One client covers one workspace, and every call is logged on the Activity page. Assistants cannot raise their own access (https://gbrain.io/docs/workspace/memory-anywhere).
- **Self-hosted:** `gbrain serve` (stdio), `gbrain serve --http` (OAuth 2.1, scopes `read`/`write`/`admin`/`agent`, admin page at `/admin`), and `gbrain mcp expose [--funnel]`. `--surface verbs` exposes seven verbs: `recall remember entity synthesize forget context_pack delta` (README).

## 4. Open source
Yes. The repo has `src/`, `docs/`, plugins for Claude and Codex, `skills/` and evals. Install with `bun install -g github:garrytan/gbrain`; do not use npm, because the `gbrain` package on npm is unrelated. A keyless local brain is `gbrain init --pglite --no-embedding`.

# Plan-changing facts
1. **The local Memorable store is encrypted and the CLI is closed source.** Pull training data through `memorable list --json` (and `chain --json`), not by reading `procedures.jsonl`. Reverse engineering is forbidden by the license.
2. **Failed runs are not a documented, retrievable part of a procedure.** Outcomes go to `stats.json` and refusals to `rejected.jsonl`. Negative examples would have to come from those files or from our own traces.
3. **The fastest source of raw training data needs no account:** `memorable install-hooks codex` writes per-turn trace JSON to `~/.memorable/traces/`. Alternatively we can POST our own traces to `/v1/extract` and keep the drafts, which have a stable, deterministic `steps[]` schema.
4. **For GRADUATED.md, run a local gbrain.** `gbrain put graduated < GRADUATED.md`, or an MCP `put_page`, is the simplest write. Hosted gbrain.io needs MCP with Full access, since its CLI has no memory commands.
5. **The Memorable docs contradict themselves** on whether the service stores procedures and on anonymous keys. Check `memorable status` live before the demo relies on either.
