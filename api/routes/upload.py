"""Check a new export. One request, everything the Upload tab needs.

The file is read from the request body into memory, run through the same
loader and the same integrity battery as the history, summarised twice —
in units, and in a currency: the file's own, or another one converted at
today's ECB rate (:mod:`api.fx`) — and forgotten. Nothing is written to disk
and nothing is kept between requests.

Two views rather than one because they differ in more than a label: the
stake buckets are cut on the stake column, and in the currency view that
column is in currency. Switching between the two is therefore a client-side
choice between two precomputed views. The unit and the currency each need a
new request, because each changes every amount and every stake bucket.
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
from api import fx, schemas, serialise
from api.explorer import ExploreSource

router = APIRouter(prefix="/api", tags=["upload"])


def _view(frame: pd.DataFrame, currency: str) -> schemas.UploadView:
    matched = loader.matched(frame)
    return schemas.UploadView(
        currency=currency,
        matched=serialise.totals(matched),
        cumulative=serialise.period_series(matched),
        breakdown=serialise.breakdown(agg.with_dimensions(matched)),
        explore_options=None
        if matched.empty
        else ExploreSource.for_upload(frame, currency).options,
    )


def _load(payload: bytes, name: str) -> pd.DataFrame:
    try:
        # SchemaError is a ValueError; so are pandas' own parse failures.
        return loader.load_upload(io.BytesIO(payload), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def convert(
    frame: pd.DataFrame, target: str | None
) -> tuple[pd.DataFrame, str, fx.Rate | None]:
    """The file in ``target`` at today's rate, or as it is when ``target`` is
    ``None`` or already its currency. Returns the frame, its label and the rate.

    Refuses rather than guesses: a file in units has no exchange rate, and a
    rate that cannot be fetched must not leave EUR amounts under a SEK label.
    """
    source = agg.currency_code(frame)
    if target is None or target == source:
        return frame, source, None
    if source == "units":
        raise HTTPException(
            status_code=400,
            detail="This file is in units, not a currency, so it cannot be converted.",
        )
    try:
        rate = fx.latest(source, target)
    except fx.FxUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return loader.in_currency(frame, rate.rate, target), target, rate


async def read_upload(
    file: fastapi.UploadFile, unit: float | None, currency: str | None
) -> tuple[pd.DataFrame, str]:
    """An uploaded file as a frame: in units of ``unit`` when one is given,
    otherwise in ``currency`` (converted) or the file's own. Returns the frame
    and its label. A unit is always in the file's own currency."""
    frame = _load(await file.read(), file.filename or "upload.csv")
    if unit is not None:
        return loader.to_units(frame, unit), "units"
    converted, label, _ = convert(frame, currency)
    return converted, label


@router.post("/upload", response_model=schemas.UploadResponse)
async def upload(
    file: Annotated[fastapi.UploadFile, File()],
    unit: Annotated[float | None, Form(gt=0)] = None,
    currency: Annotated[schemas.DisplayCurrency | None, Form()] = None,
) -> schemas.UploadResponse:
    name = file.filename or "upload.csv"
    frame = _load(await file.read(), name)

    typical = loader.typical_stake(frame)
    typical_stake = round(typical, 2) if typical > 0 else None
    unit_used = unit if unit is not None else (typical_stake or 1.0)

    file_currency = agg.currency_code(frame)
    shown, shown_currency, rate = convert(frame, currency)
    dimensions = agg.available_dimensions(agg.with_dimensions(frame))
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
            fx=None
            if rate is None
            else schemas.FxRate(
                base=rate.base, target=rate.target, rate=rate.rate, date=rate.date
            ),
        ),
        checks=serialise.check_report(checks.run_checks(frame)),
        report=serialise.load_report(loader.describe(frame)),
        dimensions=[
            schemas.LabelledKey(key=d.key, label=d.label) for d in dimensions
        ],
        missing_columns=list(loader.missing_columns(frame)),
        units=_view(loader.to_units(frame, unit_used), "units"),
        currency=_view(shown, shown_currency),
    )
