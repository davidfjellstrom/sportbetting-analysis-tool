"""The segment explorer, one request per change of filter or grouping.

Everything a person can then toggle without a round trip — how many groups to
chart, which groups to compare, P/L or ROI — is answered from this one
response: the table carries every group, ``bars_order`` the turnover order to
truncate for the bar chart, and ``curves`` a series for every group big enough
to compare.

Two routes, one computation (:mod:`api.explorer`). ``GET /api/explore``
explores the history. ``POST /api/explore/upload`` explores a file the browser
sends along with every request: the server keeps nothing between requests, so
the file is read, explored and forgotten each time, exactly as on upload.
"""

from __future__ import annotations

from typing import Annotated

import fastapi
from fastapi import APIRouter, Depends, File, Form, Response

import loader
from api import explorer, schemas
from api.history import History, get_history
from api.routes.history import CDN_CACHE
from api.routes.upload import read_upload

router = APIRouter(prefix="/api", tags=["explore"])


@router.get("/explore", response_model=schemas.ExploreResponse)
def explore(
    history: Annotated[History, Depends(get_history)],
    params: Annotated[explorer.ExploreParams, Depends()],
    response: Response,
) -> schemas.ExploreResponse:
    response.headers["Cache-Control"] = CDN_CACHE
    return explorer.run(history.explorer, params)


@router.post("/explore/upload", response_model=schemas.ExploreResponse)
async def explore_upload(
    file: Annotated[fastapi.UploadFile, File()],
    params: Annotated[explorer.ExploreParams, Depends()],
    unit: Annotated[float | None, Form(gt=0)] = None,
    currency: Annotated[schemas.DisplayCurrency | None, Form()] = None,
) -> schemas.ExploreResponse:
    """Explore an uploaded file. With ``unit`` the amounts are in units of that
    size, as on the Upload tab; without it they are in ``currency``, converted
    at today's rate, or in the file's own currency."""
    frame, currency_label = await read_upload(file, unit, currency)
    if loader.matched(frame).empty:
        return schemas.ExploreStopped(
            status="empty", message="No bet in this file was matched."
        )
    return explorer.run(
        explorer.ExploreSource.for_upload(frame, currency_label), params
    )
