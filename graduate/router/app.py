"""The proxy on :4141. POST /v1/chat/completions is #13."""
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI(title="GRADUATE router")


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"
