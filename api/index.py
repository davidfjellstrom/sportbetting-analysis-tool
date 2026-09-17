"""The API: a thin layer over the modules in src/.

Routing, validation and serialisation live here; every figure is computed by
``src/aggregations.py`` on frames produced by ``src/loader.py`` and checked
by ``src/checks.py``. The React app in ``frontend/`` displays what this
returns and computes nothing itself.

Run locally with:  uvicorn api.index:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from api.routes import explore, history, upload

app = FastAPI(
    title="Sportmarket analysis API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
app.include_router(history.router)
app.include_router(explore.router)
app.include_router(upload.router)
