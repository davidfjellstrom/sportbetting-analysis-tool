"""From frames and reports to response models. No arithmetic lives here."""

from __future__ import annotations

import math

import pandas as pd

import aggregations as agg
import checks
import loader
from api import schemas


def _finite(value: float) -> float | None:
    """JSON has no NaN; a missing figure is ``null``, never ``"NaN"``."""
    value = float(value)
    return value if math.isfinite(value) else None


def check_report(report: checks.CheckReport) -> schemas.CheckReport:
    return schemas.CheckReport(
        checks=[
            schemas.Check(
                name=c.name,
                passed=c.passed,
                severity=c.severity.value,
                detail=c.detail,
            )
            for c in report.checks
        ],
        ok=report.ok,
        n_errors=len(report.errors),
        n_warnings=len(report.warnings),
    )


def load_report(report: loader.LoadReport) -> schemas.LoadReport:
    def day(ts: pd.Timestamp | None) -> str | None:
        return None if ts is None or pd.isna(ts) else ts.strftime("%Y-%m-%d")

    return schemas.LoadReport(
        n_rows=report.n_rows,
        n_bets=report.n_bets,
        n_fixtures=report.n_fixtures,
        n_unmatched_rows=report.n_unmatched_rows,
        unmatched_row_share=report.unmatched_row_share,
        turnover=report.turnover,
        date_min=day(report.date_min),
        date_max=day(report.date_max),
        price_adjusted_coverage=report.price_adjusted_coverage,
    )


def totals(matched: pd.DataFrame) -> schemas.Totals:
    return schemas.Totals(
        turnover=float(matched["turnover"].sum()),
        pl=float(matched["pl"].sum()),
        bets=int(matched["n_bets"].fillna(0).sum()),
        fixtures=int(matched["fixture_id"].nunique()),
    )


def period_series(matched: pd.DataFrame) -> schemas.PeriodSeries:
    table, _, label = agg.by_period(matched)
    return schemas.PeriodSeries(
        bucket="day" if label == "Day" else "month",
        points=[
            schemas.PeriodPoint(
                period=row.period.strftime("%Y-%m-%d"),
                label=row.label,
                tick=row.tick,
                turnover=row.turnover,
                pl=row.pl,
                cumulative_pl=row.cumulative_pl,
            )
            for row in table.itertuples(index=False)
        ],
    )


def slice_rows(table: pd.DataFrame) -> list[schemas.SliceRow]:
    return [
        schemas.SliceRow(
            slice=row.slice,
            bets=int(row.bets),
            fixtures=int(row.fixtures),
            bets_per_fixture=row.bets_per_fixture,
            turnover=row.turnover,
            pl=row.pl,
            roi_pct=row.roi_pct,
        )
        for row in table.itertuples(index=False)
    ]


def curves(monthly: pd.DataFrame) -> dict[str, list[schemas.CurvePoint]]:
    out: dict[str, list[schemas.CurvePoint]] = {}
    for name, part in monthly.groupby("slice", observed=True, sort=False):
        out[str(name)] = [
            schemas.CurvePoint(
                month=row.month.strftime("%Y-%m-%d"),
                cum_pl=row.cum_pl,
                cum_turnover=row.cum_turnover,
                cum_roi_pct=row.cum_roi_pct,
            )
            for row in part.itertuples(index=False)
        ]
    return out


def breakdown(
    matched_with_dims: pd.DataFrame,
) -> dict[str, list[schemas.SliceRow]]:
    """Every dimension at once, largest turnover first, as the Upload tab shows."""
    return {
        d.key: slice_rows(
            agg.aggregate(matched_with_dims, d.column).sort_values(
                "turnover", ascending=False
            )
        )
        for d in agg.DIMENSIONS
    }


def fill_rate(frame: pd.DataFrame) -> float | None:
    return _finite(loader.fill_rate(frame))
