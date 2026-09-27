"""GET /app: the product frontend (ui/app/). Its CSS and JS load from /ui/app/ through state.py's /ui mount; every
number on it comes from the live APIs (/state, /api/swarm, /api/consent, /api/sample, /bench/latest/results.json)."""

from pathlib import Path

from fastapi.responses import FileResponse

from graduate.router.app import app

PAGE = Path(__file__).resolve().parents[2] / "ui" / "app" / "index.html"


@app.get("/app", include_in_schema=False)
def product_app():
    return FileResponse(PAGE, media_type="text/html")
