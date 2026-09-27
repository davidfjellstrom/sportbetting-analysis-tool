"""The segment explorer, for whichever data is being explored.

The history and an uploaded file go through the same code here, so a figure in
the explorer means the same thing whichever of the two it was computed from.
What differs is captured once, in an :class:`ExploreSource`: which columns the
data has, how big a slice must be to earn a curve, and whether curves run by
day or by month.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import Query

import aggregations as agg
import loader
from api import schemas, serialise


@dataclass(frozen=True)
class ExploreParams:
    """One explorer request: the filters, the grouping and the sort.

    Declared once, as a FastAPI dependency, so the history route and the
    upload route take exactly the same query parameters.
    """

    group_by: schemas.DimensionKey = "market_type"
    sort: schemas.SortKey = "turnover_desc"
    min_fixtures: Annotated[int, Query(ge=0)] = 0
    date_from: date | None = None
    date_to: date | None = None
    min_stake: Annotated[float, Query(ge=0)] = 0.0
    max_stake: Annotated[float | None, Query(ge=0)] = None
    market_type: Annotated[list[str] | None, Query()] = None
    bookie: Annotated[list[str] | None, Query()] = None
    #: Split every group by selection too ("pinnacle · home"). Ignored where
    #: the grouping is not in ``ExploreOptions.splittable_by_selection``.
    split_by_selection: bool = False


@dataclass(frozen=True)
class ExploreSource:
    """Everything the explorer needs to know about the data it explores."""

    frame: pd.DataFrame
    currency: str
    curve_rule: agg.CurveRule
    curve_freq: str
    options: schemas.ExploreOptions
    #: Whether a response carries the running P/L of the rows in view.
    over_time: bool = False

    @classmethod
    def build(
        cls,
        matched: pd.DataFrame,
        currency: str,
        curve_rule: agg.CurveRule,
        unit: float = 1.0,
    ) -> ExploreSource:
        """``matched`` is the matched rows only, as from :func:`loader.matched`;
        ``unit`` is one unit in its amounts, for the position sizes."""
        frame = agg.with_dimensions(matched, unit)
        dims = agg.available_dimensions(frame)
        options = schemas.ExploreOptions(
            currency=currency,
            date_min=frame["event_day"].min().strftime("%Y-%m-%d"),
            date_max=frame["event_day"].max().strftime("%Y-%m-%d"),
            stake_ceiling=agg.stake_ceiling(frame),
            # An empty list hides the filter: the column is not in the file.
            market_types=agg.option_values(frame, "market_type")
            if "market_type" in frame.columns
            else [],
            bookies=agg.option_values(frame, "bookie")
            if "bookie" in frame.columns
            else [],
            dimensions=[serialise.dimension(d) for d in dims],
            # Empty when the data has no side to split by.
            splittable_by_selection=[d.key for d in dims if d.splittable]
            if "selection" in frame.columns
            else [],
            sorts=[schemas.LabelledKey(key=s.key, label=s.label) for s in agg.SORTS],
            compare=schemas.CompareRules(
                min_turnover=curve_rule.min_turnover,
                min_bets=curve_rule.min_bets,
                min_fixtures=curve_rule.min_fixtures,
                max_series=agg.MAX_SERIES,
            ),
        )
        return cls(frame, currency, curve_rule, agg.curve_freq(frame), options)

    @classmethod
    def for_upload(
        cls, frame: pd.DataFrame, currency: str, unit: float
    ) -> ExploreSource:
        """An uploaded file, already in the amounts it is to be shown in."""
        matched = loader.matched(frame)
        source = cls.build(matched, currency, agg.upload_curve_rule(matched), unit)
        return dataclasses.replace(source, over_time=True)


def run(source: ExploreSource, params: ExploreParams) -> schemas.ExploreResponse:
    if params.group_by not in {d.key for d in source.options.dimensions}:
        return schemas.ExploreStopped(
            status="empty", message="This data cannot be grouped that way."
        )
    try:
        frame = agg.apply_filters(
            source.frame,
            agg.Filters(
                date_from=params.date_from,
                date_to=params.date_to,
                min_stake=params.min_stake,
                max_stake=params.max_stake,
                market_types=tuple(params.market_type or ()),
                bookies=tuple(params.bookie or ()),
            ),
            source.options.stake_ceiling,
        )
    except agg.StakeRangeError as exc:
        return schemas.ExploreStopped(status="stake_range_invalid", message=str(exc))
    if frame.empty:
        return schemas.ExploreStopped(
            status="empty", message="No rows match those filters."
        )

    dimension = agg.DIMENSION_BY_KEY[params.group_by]
    split = (
        params.split_by_selection
        and dimension.key in source.options.splittable_by_selection
    )
    columns = [dimension.column, "selection"] if split else [dimension.column]
    table_all = agg.aggregate(frame, columns)
    table = table_all
    if params.min_fixtures:
        table = table[table["fixtures"] >= params.min_fixtures]
    table = agg.sort_table(table, agg.SORT_BY_KEY[params.sort])

    eligible = agg.eligible_for_curves(table_all, source.curve_rule)
    curves = agg.cumulative_by_slice(frame, columns, source.curve_freq)
    curves = curves[curves["slice"].isin(eligible["slice"])]

    totals = serialise.totals(frame)
    return schemas.ExploreOk(
        currency=source.currency,
        view=schemas.ViewTotals(
            **totals.model_dump(), roi_pct=100 * totals.pl / totals.turnover
        ),
        groups_shown=len(table),
        groups_total=len(table_all),
        table=serialise.slice_rows(table),
        bars_order=list(table.sort_values("turnover", ascending=False)["slice"]),
        eligible=list(eligible["slice"]),
        curves=serialise.curves(curves),
        curve_bucket="day" if source.curve_freq == "D" else "month",
        cumulative=serialise.period_series(frame) if source.over_time else None,
    )
