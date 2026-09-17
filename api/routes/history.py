"""What is loaded: the Overview tab and the explorer's filter options.

Both depend on the deployed data alone, so the responses are precomputed in
:mod:`api.history` and marked cacheable at the CDN. Vercel keys its cache per
deployment, and the data only changes with a deployment, so a long
``s-maxage`` is safe; ``max-age=0`` keeps browsers from holding a stale copy
across deployments.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from api import schemas
from api.history import History, get_history

router = APIRouter(prefix="/api", tags=["history"])

CDN_CACHE = "public, max-age=0, s-maxage=31536000"


@router.get("/overview", response_model=schemas.OverviewResponse)
def overview(
    history: Annotated[History, Depends(get_history)], response: Response
) -> schemas.OverviewResponse:
    response.headers["Cache-Control"] = CDN_CACHE
    return history.overview


@router.get("/explore/options", response_model=schemas.ExploreOptions)
def explore_options(
    history: Annotated[History, Depends(get_history)], response: Response
) -> schemas.ExploreOptions:
    response.headers["Cache-Control"] = CDN_CACHE
    return history.options
