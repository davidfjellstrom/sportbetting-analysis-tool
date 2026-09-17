"""The API: a thin layer over the modules in src/.

Routing, validation and serialisation live here; every figure is computed by
``src/aggregations.py`` on frames produced by ``src/loader.py`` and checked
by ``src/checks.py``. The React app in ``frontend/`` displays what this
returns and computes nothing itself.

Run locally with:  uvicorn api.index:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from api.routes import explore, history, upload

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

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

# The built React app, served from the same origin as the API. On Vercel the
# files are promoted to the CDN at build time and never reach the function;
# locally uvicorn serves them itself once `npm run build` has run. The
# directory is not required to exist, so the API imports (and its tests run)
# on a machine that has not built the frontend.
app.frontend("/", directory=FRONTEND_DIST, check_dir=False)
