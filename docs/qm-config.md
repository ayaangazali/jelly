# QM bring-up (custom provider)

QM ([yc-software/qm](https://github.com/yc-software/qm)) runs locally and sends its model calls to an OpenAI-compatible endpoint that we register as the custom provider `graduate`. This is proven against a stub. The live QM demo is #27.

Tested on 2026-09-27 against QM `a5a3667` with Node 24.19.0. The fleet host already had Node and Docker.

## 1. Clone and install

```bash
git clone --depth 1 https://github.com/yc-software/qm.git && cd qm
npm ci --no-audit --no-fund
```

## 2. Minimum `.env`

Put this `.env` in the QM checkout. It holds no secrets and no provider keys.

```bash
PORT=18788
ORG_ID=acme
HARNESS=pi
ALLOW_UNAUTHENTICATED_CORE=1
ADMIN_GRANTS=dev@example.com:org_admin
```

- `ALLOW_UNAUTHENTICATED_CORE=1` lets you run with none of the `CORE_SIGNING_SECRET` / `CAPABILITY_SECRET` / `PORTAL_IDENTITY_SECRET` signing secrets and use plain `curl`. Without it, core refuses to start unless `CORE_SIGNING_SECRET` has at least 32 characters, and every request then needs HMAC `x-signature` / `x-timestamp` headers. Use it on localhost only.
- `ADMIN_GRANTS` is needed for the admin routes. Send `x-admin-actor: dev@example.com@acme` with those requests.
- `HARNESS=pi` is the default. Custom models only work with pi.
- With no `DATABASE_URL`, sessions and the provider registration live in memory, so repeat step 5 after every restart. Neither Postgres nor Docker is needed.
- Any free `PORT` works. 18788 avoids ports that other services on the fleet host already use.

## 3. Start the stub

The real router owns `:4141`, so the stub uses `:4142`. QM always streams (`stream: true`), so the stub answers in SSE only.

```bash
cat > stub.py <<'EOF'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        print("POST", self.path, "model=" + body["model"], self.headers["authorization"], flush=True)
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        for delta, stop in (({"role": "assistant", "content": "stub says hi"}, None), ({}, "stop")):
            chunk = {"id": "stub", "object": "chat.completion.chunk", "model": body["model"],
                     "choices": [{"index": 0, "delta": delta, "finish_reason": stop}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

HTTPServer(("127.0.0.1", 4142), H).serve_forever()
EOF
python3 stub.py
```

## 4. Start QM

Run this in the QM checkout, in a second terminal:

```bash
node --env-file=.env src/index.ts
```

It is ready when it prints `[qm] listening on :18788 (org=acme, store=memory, ...)`. `npm start` does the same thing but rebuilds the connector SDK first.

## 5. Register the provider and enable the model

`provider.json`:

```json
{"name":"GRADUATE","protocol":"openai","baseUrl":"http://127.0.0.1:4142/v1","models":[{"id":"graduate","contextWindow":32768,"maxTokens":4096}],"apiKey":"sess-0123456789ab","validate":false}
```

```bash
A='x-admin-actor: dev@example.com@acme'
curl -sS -X PUT localhost:18788/v1/admin/custom-providers/graduate -H "$A" -H 'content-type: application/json' -d @provider.json
curl -sS -X PUT localhost:18788/v1/admin/scopes/org:acme/webui-models -H "$A" -H 'content-type: application/json' -d '{"ids":["graduate"]}'
```

- `protocol: "openai"` means chat completions, and QM calls `POST {baseUrl}/chat/completions`.
- `validate: false` skips the `GET {baseUrl}/models` check. The router does not serve `/models`.
- `apiKey` arrives as `Authorization: Bearer <apiKey>`. The router reads the bearer as the session id (`sess-` plus 12 hex characters, see `graduate/contracts.md`). QM sends the same key on every call, so one registration is one GRADUATE session. To start a new session, PUT the provider again with a new `apiKey`.
- Without the `webui-models` PUT, a turn with `surface: "web"` and `model: "graduate"` gets `{"status":"refused","reason":"that model is not enabled for the web UI"}`.
- For the real router, change `baseUrl` to `http://127.0.0.1:4141/v1`.

## 6. Send one message

```bash
curl -sS -X POST localhost:18788/v1/turns -H 'content-type: application/json' -d '{"surface":"web","actor":{"externalId":"dev@example.com"},"conversation":{"kind":"dm","threadRef":"web:dev@example.com:qm-stub-1"},"text":"Say hi","origin":{"kind":"human"},"addressed":true,"model":"graduate"}'
```

Expected response: `{"status":"ok","sessionId":"…","reply":"stub says hi",…}`. The stub prints:

```
POST /v1/chat/completions model=graduate Bearer sess-0123456789ab
```

For each new conversation, use a new `threadRef` that starts with `web:dev@example.com:`.

## Bring-up time

The first run took **2 min 31 s** of wall-clock time, from the start of `git clone` (08:13:29 UTC) to the first request logged by the stub (08:16:00 UTC). That includes `npm ci` (34 s) and three fixes: a port conflict, the missing `ADMIN_GRANTS`, and the missing `webui-models` PUT. With this page, someone new should need about 5 minutes.

## Not covered

- Tool calls. The stub never asks for one, so QM never started a sandbox. A real agent that runs commands needs the local sandbox (Docker plus `npm run sandbox:local:build`) or `npm run dev-instance:web`, which also starts Postgres in Docker.
- The web UI and admin UI. Everything above goes through the HTTP API. The admin UI can do the same provider setup (Settings, Providers), but that was not tested.
