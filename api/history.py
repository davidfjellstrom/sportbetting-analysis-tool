"""The loaded history: read once per process, shared read-only by every request.

On Vercel one function instance serves many requests, and with Fluid compute
several at a time. Parsing 15 MB of CSV per request would dominate every
response, so the frame — and everything derived from it that does not depend
on a request — is computed on first use and kept. Nothing here is ever
mutated afterwards; every consumer filters into a new frame.

The app reads ``data/processed/`` only: the exports rescaled to notional
units by ``python src/loader.py``. The raw EUR files never need to be where
the app runs (CLAUDE.md -> Privacy).
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

import pandas as pd
from fastapi import HTTPException

import aggregations as agg
import checks
import loader
from api import schemas, serialise
from api.explorer import ExploreSource

NO_DATA_MESSAGE = (
    "No processed data. On the machine that holds the raw exports, run "
    "`python src/loader.py` to write `data/processed/` in units, then "
    "deploy that directory."
)


@dataclass(frozen=True)
class History:
    frame: pd.DataFrame
    matched: pd.DataFrame
    explore_frame: pd.DataFrame
    explorer: ExploreSource
    currency: str
    report: loader.LoadReport
    checks: checks.CheckReport
    overview: schemas.OverviewResponse
    options: schemas.ExploreOptions

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> History:
        matched = loader.matched(frame)
        currency = agg.currency_code(frame)
        explorer = ExploreSource.build(matched, currency, agg.history_curve_rule())
        report = loader.describe(frame)
        integrity = checks.run_checks(frame)
        overview = schemas.OverviewResponse(
            currency=currency,
            matched=serialise.totals(matched),
            fill_rate=serialise.fill_rate(frame),
            report=serialise.load_report(report),
            checks=serialise.check_report(integrity),
            cumulative=serialise.period_series(matched),
        )
        return cls(
            frame=frame,
            matched=matched,
            explore_frame=explorer.frame,
            explorer=explorer,
            currency=currency,
            report=report,
            checks=integrity,
            overview=overview,
            options=explorer.options,
        )


@functools.cache
def load_history() -> History:
    return History.from_frame(loader.load_raw(loader.DEFAULT_PROCESSED_DIR))


def get_history() -> History:
    """FastAPI dependency. Tests override it with a synthetic frame."""
    try:
        return load_history()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=NO_DATA_MESSAGE) from exc
