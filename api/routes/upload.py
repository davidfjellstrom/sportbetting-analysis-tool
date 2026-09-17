"""Check a new export. One request, everything the Upload tab needs.

The file is read from the request body into memory, run through the same
loader and the same integrity battery as the history, summarised twice —
in units and in the currency the file says it is in — and forgotten. Nothing
is written to disk and nothing is kept between requests.

Two views rather than one because they differ in more than a label: the
stake buckets are cut on the stake column, and in the currency view that
column is in currency. Switching between the two is therefore a client-side
choice between two precomputed views. Only the unit itself needs a new
request, because it changes every amount and every stake bucket.
"""

from __future__ import annotations

import io
from typing import Annotated

import fastapi
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException

import aggregations as agg
import checks
import loader
from api import schemas, serialise

router = APIRouter(prefix="/api", tags=["upload"])


def _view(frame: pd.DataFrame, currency: str) -> schemas.UploadView:
    matched = loader.matched(frame)
    return schemas.UploadView(
        currency=currency,
        matched=serialise.totals(matched),
        cumulative=serialise.period_series(matched),
        breakdown=serialise.breakdown(agg.with_dimensions(matched)),
    )


@router.post("/upload", response_model=schemas.UploadResponse)
async def upload(
    file: Annotated[fastapi.UploadFile, File()],
    unit: Annotated[float | None, Form(gt=0)] = None,
) -> schemas.UploadResponse:
    name = file.filename or "upload.csv"
    payload = await file.read()
    try:
        # SchemaError is a ValueError; so are pandas' own parse failures.
        frame = loader.load_upload(io.BytesIO(payload), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    typical = loader.typical_stake(frame)
    typical_stake = round(typical, 2) if typical > 0 else None
    unit_used = unit if unit is not None else (typical_stake or 1.0)

    file_currency = agg.currency_code(frame)
    currency_in_file = (
        None if "currency" not in frame.columns or file_currency == "units"
        else file_currency
    )
    return schemas.UploadResponse(
        file=schemas.UploadFile(
            name=name,
            currency_in_file=currency_in_file,
            typical_stake=typical_stake,
            unit_used=unit_used,
        ),
        checks=serialise.check_report(checks.run_checks(frame)),
        report=serialise.load_report(loader.describe(frame)),
        units=_view(loader.to_units(frame, unit_used), "units"),
        currency=_view(frame, file_currency),
    )
