"""The segment explorer, one request per change of filter or grouping.

Everything a person can then toggle without a round trip — how many groups to
chart, which groups to compare, P/L or ROI — is answered from this one
response: the table carries every group, ``bars_order`` the turnover order to
truncate for the bar chart, and ``curves`` a monthly series for every group
big enough to compare.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

import aggregations as agg
from api import schemas, serialise
from api.history import History, get_history
from api.routes.history import CDN_CACHE

router = APIRouter(prefix="/api", tags=["explore"])


@router.get("/explore", response_model=schemas.ExploreResponse)
def explore(
    history: Annotated[History, Depends(get_history)],
    response: Response,
    group_by: schemas.DimensionKey = "market_type",
    sort: schemas.SortKey = "turnover_desc",
    min_fixtures: Annotated[int, Query(ge=0)] = 0,
    date_from: date | None = None,
    date_to: date | None = None,
    min_stake: Annotated[float, Query(ge=0)] = 0.0,
    max_stake: Annotated[float | None, Query(ge=0)] = None,
    market_type: Annotated[list[str] | None, Query()] = None,
    bookie: Annotated[list[str] | None, Query()] = None,
) -> schemas.ExploreResponse:
    response.headers["Cache-Control"] = CDN_CACHE
    ceiling = history.options.stake_ceiling
    try:
        frame = agg.apply_filters(
            history.explore_frame,
            agg.Filters(
                date_from=date_from,
                date_to=date_to,
                min_stake=min_stake,
                max_stake=max_stake,
                market_types=tuple(market_type or ()),
                bookies=tuple(bookie or ()),
            ),
            ceiling,
        )
    except agg.StakeRangeError as exc:
        return schemas.ExploreStopped(status="stake_range_invalid", message=str(exc))
    if frame.empty:
        return schemas.ExploreStopped(
            status="empty", message="No rows match those filters."
        )

    dimension = agg.DIMENSION_BY_KEY[group_by]
    table_all = agg.aggregate(frame, dimension.column)
    table = table_all
    if min_fixtures:
        table = table[table["fixtures"] >= min_fixtures]
    table = agg.sort_table(table, agg.SORT_BY_KEY[sort])

    eligible = agg.eligible_for_curves(table_all)
    monthly = agg.cumulative_by_slice(frame, dimension.column)
    monthly = monthly[monthly["slice"].isin(eligible["slice"])]

    turnover = float(frame["turnover"].sum())
    pl = float(frame["pl"].sum())
    return schemas.ExploreOk(
        currency=history.currency,
        view=schemas.ViewTotals(
            turnover=turnover,
            pl=pl,
            roi_pct=100 * pl / turnover,
            bets=int(frame["n_bets"].fillna(0).sum()),
        ),
        groups_shown=len(table),
        groups_total=len(table_all),
        table=serialise.slice_rows(table),
        bars_order=list(table.sort_values("turnover", ascending=False)["slice"]),
        eligible=list(eligible["slice"]),
        curves=serialise.curves(monthly),
    )
