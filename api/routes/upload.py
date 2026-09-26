"""Check a new export. One request, everything the Upload tab needs.

The file is read from the request body into memory, run through the same
loader and the same integrity battery as the history, summarised twice —
in units, and in a currency: the file's own, or another one converted at
today's ECB rate (:mod:`api.fx`) — and forgotten. Nothing is written to disk
and nothing is kept between requests.

Two views, units and a currency, computed together so that switching between
them is a client-side choice. The unit and the currency each need a new
request, because each changes every amount.

A unit is a stake in the currency on screen: "1 unit = 100 SEK" when the file
is shown in SEK. The file is converted first and then divided by the unit.
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


def _view(frame: pd.DataFrame, currency: str, unit: float) -> schemas.UploadView:
    """One view of the file. ``unit`` is one unit in this view's amounts."""
    matched = loader.matched(frame)
    return schemas.UploadView(
        currency=currency,
        matched=serialise.totals(matched),
        cumulative=serialise.period_series(matched),
        breakdown=serialise.breakdown(agg.with_dimensions(matched, unit)),
        explore_options=None
        if matched.empty
        else ExploreSource.for_upload(frame, currency, unit).options,
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


def unit_in(unit: float, unit_currency: str | None, shown: str) -> float:
    """A unit set in ``unit_currency``, expressed in the currency on screen.

    Switching from EUR to SEK keeps "1 unit = 30 EUR" worth the same, rather
    than turning it into 30 SEK. A file in units has no currency to convert to.
    """
    if unit_currency is None or unit_currency == shown or shown == "units":
        return unit
    try:
        rate = fx.latest(unit_currency, shown)
    except fx.FxUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return round(unit * rate.rate, 2)


def _typical_unit(frame: pd.DataFrame) -> tuple[float | None, float]:
    """The typical stake (``None`` when nothing matched) and the unit it gives."""
    typical = loader.typical_stake(frame)
    typical_stake = round(typical, 2) if typical > 0 else None
    return typical_stake, typical_stake or 1.0


async def read_upload(
    file: fastapi.UploadFile, unit: float | None, currency: str | None, in_units: bool
) -> tuple[pd.DataFrame, str, float]:
    """An uploaded file as a frame, in ``currency`` (converted) or the file's
    own, and then in units of ``unit`` when ``in_units``. Returns the frame, its
    label and one unit in its amounts; ``unit`` defaults to the typical stake."""
    frame = _load(await file.read(), file.filename or "upload.csv")
    converted, label, _ = convert(frame, currency)
    unit = unit if unit is not None else _typical_unit(converted)[1]
    if in_units:
        return loader.to_units(converted, unit), "units", 1.0
    return converted, label, unit


@router.post("/upload", response_model=schemas.UploadResponse)
async def upload(
    file: Annotated[fastapi.UploadFile, File()],
    unit: Annotated[float | None, Form(gt=0)] = None,
    currency: Annotated[schemas.DisplayCurrency | None, Form()] = None,
    unit_currency: Annotated[schemas.DisplayCurrency | None, Form()] = None,
) -> schemas.UploadResponse:
    """``unit`` is in ``unit_currency``, or in the currency shown when that is
    left out; the response gives it back in the currency shown."""
    name = file.filename or "upload.csv"
    frame = _load(await file.read(), name)

    file_currency = agg.currency_code(frame)
    shown, shown_currency, rate = convert(frame, currency)

    typical_stake, typical_unit = _typical_unit(shown)
    unit_used = (
        unit_in(unit, unit_currency, shown_currency)
        if unit is not None
        else typical_unit
    )
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
        dimensions=[serialise.dimension(d) for d in dimensions],
        missing_columns=list(loader.missing_columns(frame)),
        units=_view(loader.to_units(shown, unit_used), "units", 1.0),
        currency=_view(shown, shown_currency, unit_used),
    )
