"""The API contract, as pydantic models.

``frontend/src/api/types.ts`` mirrors these one to one. A field added here
without a matching TypeScript type is a bug in the frontend build, not in
this file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

DimensionKey = Literal[
    "market_type",
    "selection",
    "bookie",
    "country",
    "competition",
    "market",
    "event_type",
    "stake_bucket",
    "n_bets_bucket",
    "year",
    "month",
    "weekday",
]
SortKey = Literal[
    "turnover_desc",
    "roi_desc",
    "roi_asc",
    "pl_desc",
    "fixtures_desc",
    "bets_per_fixture_desc",
    "name_asc",
]


class Check(BaseModel):
    name: str
    passed: bool
    severity: Literal["ERROR", "WARN", "INFO"]
    detail: str


class CheckReport(BaseModel):
    checks: list[Check]
    ok: bool
    n_errors: int
    n_warnings: int


class LoadReport(BaseModel):
    n_rows: int
    #: ``None`` when an upload has no ``Nr of Bets``; a row is not a bet.
    n_bets: int | None
    n_fixtures: int
    n_unmatched_rows: int
    unmatched_row_share: float
    turnover: float
    date_min: str | None
    date_max: str | None
    price_adjusted_coverage: float


class Totals(BaseModel):
    turnover: float
    pl: float
    bets: int | None
    fixtures: int


class PeriodPoint(BaseModel):
    period: str
    label: str
    tick: str
    turnover: float
    pl: float
    cumulative_pl: float


class PeriodSeries(BaseModel):
    bucket: Literal["day", "month"]
    points: list[PeriodPoint]


class SliceRow(BaseModel):
    slice: str
    bets: int | None
    fixtures: int
    bets_per_fixture: float | None
    turnover: float
    pl: float
    roi_pct: float


# ---- GET /api/overview -----------------------------------------------------


class OverviewResponse(BaseModel):
    currency: str
    matched: Totals
    fill_rate: float | None
    report: LoadReport
    checks: CheckReport
    cumulative: PeriodSeries


# ---- GET /api/explore/options ------------------------------------------------


class LabelledKey(BaseModel):
    key: str
    label: str


class CompareRules(BaseModel):
    """What a group needs for its own curve. ``None``: that bar does not apply."""

    min_turnover: float
    min_bets: int | None
    min_fixtures: int | None
    max_series: int


class ExploreOptions(BaseModel):
    currency: str
    date_min: str
    date_max: str
    #: ``None`` when the data has no stake column; the stake filter is hidden.
    stake_ceiling: float | None
    #: Empty when the data has no such column; the filter is hidden.
    market_types: list[str]
    bookies: list[str]
    dimensions: list[LabelledKey]
    sorts: list[LabelledKey]
    compare: CompareRules


# ---- GET /api/explore --------------------------------------------------------


class ViewTotals(BaseModel):
    turnover: float
    pl: float
    roi_pct: float
    bets: int | None


class CurvePoint(BaseModel):
    month: str
    cum_pl: float
    cum_turnover: float
    cum_roi_pct: float


class ExploreOk(BaseModel):
    status: Literal["ok"] = "ok"
    currency: str
    view: ViewTotals
    groups_shown: int
    groups_total: int
    table: list[SliceRow]
    bars_order: list[str]
    eligible: list[str]
    curves: dict[str, list[CurvePoint]]
    #: What one point of a curve covers. ``CurvePoint.month`` holds its start.
    curve_bucket: Literal["day", "month"]


class ExploreStopped(BaseModel):
    """The explorer has nothing to show and says why, as the Streamlit app does."""

    status: Literal["stake_range_invalid", "empty"]
    message: str


ExploreResponse = ExploreOk | ExploreStopped


# ---- POST /api/upload --------------------------------------------------------


class UploadFile(BaseModel):
    name: str
    currency_in_file: str | None
    typical_stake: float | None
    unit_used: float


class UploadView(BaseModel):
    currency: str
    matched: Totals
    cumulative: PeriodSeries
    #: Keyed by the dimensions in ``UploadResponse.dimensions`` only.
    breakdown: dict[DimensionKey, list[SliceRow]]
    #: The explorer's options for this file, in this view's amounts. ``None``
    #: when no row matched: there is nothing to explore.
    explore_options: ExploreOptions | None


class UploadResponse(BaseModel):
    file: UploadFile
    checks: CheckReport
    report: LoadReport
    #: What this file can be grouped by; a subset when it left columns out.
    dimensions: list[LabelledKey]
    #: Export headers the file did not carry, e.g. ``["Bookie"]``.
    missing_columns: list[str]
    units: UploadView
    currency: UploadView
