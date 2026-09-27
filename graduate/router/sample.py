"""GET /api/sample (#87): true when this router serves fixture state (`graduate up --demo`), so the dashboard labels
every number as sample data."""

import os

from graduate.router.app import app


@app.get("/api/sample")
def sample():
    return {"sample": os.environ.get("GRADUATE_SAMPLE") == "1"}
