"""What the apps show, computed once, in one place.

The API behind the React app calls these functions and nothing else for its
figures, so every number on screen is one the tests in
``tests/test_aggregations.py`` cover.

Everything here is presentation-level: bins for an explorer to group by,
per-slice totals, per-period totals. None of it is an analysis feature, none
of it carries an interval. Two rules from CLAUDE.md are load-bearing all the
same:

* ROI is turnover-weighted, ``sum(pl) / sum(turnover)``, never the mean of the
  export's per-row ROI column.
* Slices are grouped with ``dropna=False``: rows without a ``selection`` form
  their own visible category, ``(no value)``, instead of vanishing from every
  total that touches the column.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

# --------------------------------------------------------------------------
# Vocabulary: what can be grouped by, how it can be sorted
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Dimension:
    """One thing the explorer can group by.

    ``key`` is the stable identifier the API speaks, ``label`` what a person
    reads, ``column`` where the values live after :func:`with_dimensions`,
    ``help`` a line for the person when the label alone does not say enough.
    """

    key: str
    label: str
    column: str
    help: str | None = None
    #: Whether "Split by selection" is offered. Not for Selection itself, and
    #: not for Competition, whose groups are too many to split again.
    splittable: bool = True


#: Raw export columns first, then bins derived here for presentation only.
DIMENSIONS: tuple[Dimension, ...] = (
    Dimension("market_type", "Market type", "market_type"),
    Dimension("selection", "Selection", "selection", splittable=False),
    Dimension("bookie", "Bookie", "bookie"),
    Dimension("country", "Country", "country"),
    Dimension("competition", "Competition", "competition", splittable=False),
    Dimension("market", "Market (sport / period)", "market"),
    Dimension("event_type", "Event type", "event_type"),
    Dimension(
        "position_size",
        "Position size",
        "_position_size",
        help="Total matched on one selection in one match at one bookie, in units.",
    ),
    Dimension("n_bets_bucket", "Bets aggregated on the row", "_n_bets_bucket"),
    Dimension("year", "Year", "_year"),
    Dimension("month", "Month", "_month"),
    Dimension("weekday", "Weekday", "_weekday"),
)
DIMENSION_BY_KEY: dict[str, Dimension] = {d.key: d for d in DIMENSIONS}


@dataclass(frozen=True)
class Sort:
    key: str
    label: str
    column: str
    ascending: bool


SORTS: tuple[Sort, ...] = (
    Sort("turnover_desc", "Turnover (largest first)", "turnover", False),
    Sort("roi_desc", "ROI (best first)", "roi_pct", False),
    Sort("roi_asc", "ROI (worst first)", "roi_pct", True),
    Sort("pl_desc", "P/L (largest first)", "pl", False),
    Sort("fixtures_desc", "Matches (most first)", "fixtures", False),
    Sort(
        "bets_per_fixture_desc",
        "Bets per match (most first)",
        "bets_per_fixture",
        False,
    ),
    Sort("name_asc", "Name", "slice", True),
)
SORT_BY_KEY: dict[str, Sort] = {s.key: s for s in SORTS}

#: A position's matched turnover in units: 1 is one unit, whatever the amounts
#: are shown in. Left-closed: 0.5 is "0.5-1 u".
POSITION_BINS: list[float] = [0, 0.5, 1, 2, 3, 5, 10, float("inf")]
POSITION_LABELS: list[str] = [
    "<0.5 u", "0.5-1 u", "1-2 u", "2-3 u", "3-5 u", "5-10 u", "10+ u"
]

#: Right-closed, so 1 is "1", 2 is "2", anything above is "3+".
N_BETS_BINS: list[float] = [0, 1, 2, float("inf")]
N_BETS_LABELS: list[str] = ["1", "2", "3+"]

#: A slice needs both to be worth its own cumulative curve. Turnover alone
#: lets a handful of huge bets in; bet count alone lets a long tail of tiny
#: ones in. Requiring both keeps the grid to the segments that actually have a
#: history to show.
SMALL_MULTIPLE_MIN_TURNOVER = 350.0  # units; roughly 0.3% of lifetime turnover
SMALL_MULTIPLE_MIN_BETS = 2_000

#: An uploaded file is a few weeks, not four years, so the absolute bars above
#: would leave it without a single curve. For a file the bar scales with it: a
#: share of its turnover, and a floor on matches rather than bets — matches are
#: the independent unit (CLAUDE.md rule 3), and a file may not carry bet counts.
UPLOAD_CURVE_MIN_TURNOVER_SHARE = 0.02
UPLOAD_CURVE_MIN_FIXTURES = 20

#: Eight is the hard ceiling for series on one chart: the categorical palette
#: has eight validated slots, and a ninth would have to fold into "Other".
MAX_SERIES = 8

#: Below this span a frame is bucketed by day rather than by month. A fresh
#: export covers days, not years: bucketed monthly it collapses to a single
#: point, and an area chart with one point draws nothing at all.
DAILY_BUCKET_MAX_SPAN = pd.Timedelta(days=92)


# --------------------------------------------------------------------------
# Labels read from the data
# --------------------------------------------------------------------------


def currency_code(frame: pd.DataFrame) -> str:
    """The currency the amounts are in, read from the data rather than assumed.

    ``checks.check_single_currency`` guarantees there is only one, so taking the
    first is safe — and if a future export ever mixes currencies, that check
    fails loudly before this label can mislead anyone.
    """
    if "currency" in frame.columns:
        values = frame["currency"].dropna().unique()
        if len(values) == 1:
            code = str(values[0])
            return code if code == "units" else code.upper()
    return "EUR"


# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------


def with_dimensions(frame: pd.DataFrame, unit: float = 1.0) -> pd.DataFrame:
    """Attach the presentation-only bins the explorer offers.

    ``unit`` is what one unit is in the frame's amounts: 1 when they are
    already in units, the viewer's unit when they are in a currency. The
    position size is a row's matched ``turnover`` in units. A row holds every
    bet on one selection in one match at one bookie; the export does not say
    how the bets split, but their total is exact, and bets on one selection
    in one match win or lose together anyway. In units, it means the same
    thing whichever currency is on screen.

    Returns a copy; the caller's frame is left alone, which matters when that
    frame is the one cached copy of the history that every request shares.

    A bucket whose source column the export left out is not added at all, so
    :func:`available_dimensions` drops it instead of showing an empty slice.
    """
    out = frame.copy()
    out["_year"] = out["event_day"].dt.year.astype("string")
    out["_month"] = out["event_day"].dt.to_period("M").astype("string")
    out["_weekday"] = out["event_day"].dt.day_name().astype("string")
    out["_position_size"] = pd.cut(
        out["turnover"] / unit,
        bins=POSITION_BINS,
        labels=POSITION_LABELS,
        right=False,
    )
    if "n_bets" in out.columns:
        out["_n_bets_bucket"] = pd.cut(
            out["n_bets"], bins=N_BETS_BINS, labels=N_BETS_LABELS
        )
    return out


def available_dimensions(frame_with_dims: pd.DataFrame) -> tuple[Dimension, ...]:
    """The dimensions a frame can actually be grouped by.

    Always all of them for the history. An upload may leave columns out, and a
    dimension without its column is hidden rather than shown as a single
    "(no value)" slice that looks like data.
    """
    return tuple(d for d in DIMENSIONS if d.column in frame_with_dims.columns)


NO_VALUE = "(no value)"


def slice_names(frame: pd.DataFrame, columns: str | list[str]) -> pd.Series:
    """Each row's slice: its value, or its values joined, as in "pinnacle · home".

    A missing value is named, never dropped: see :func:`aggregate`.
    """
    names = None
    for column in [columns] if isinstance(columns, str) else columns:
        part = frame[column].astype("string").fillna(NO_VALUE)
        names = part if names is None else names + " · " + part
    return names


def aggregate(frame: pd.DataFrame, columns: str | list[str]) -> pd.DataFrame:
    """Turnover, P/L and ROI per slice of one column, or of two combined.

    ``dropna=False`` on purpose: a material share of rows carry no
    ``selection``, and they need not perform like the rest. Dropping them
    quietly would change every total that touches the column without saying so.

    Without an ``n_bets`` column, ``bets`` and ``bets_per_fixture`` are NaN:
    a row is not a bet, so counting rows would state a number nobody knows.
    """
    has_bets = "n_bets" in frame.columns
    grouped = (
        frame.assign(
            n_bets=frame["n_bets"] if has_bets else 0,
            slice=slice_names(frame, columns),
        )
        .groupby("slice")
        .agg(
            bets=("n_bets", "sum"),
            fixtures=("fixture_id", "nunique"),
            turnover=("turnover", "sum"),
            pl=("pl", "sum"),
        )
        .reset_index()
    )
    if not has_bets:
        grouped["bets"] = float("nan")
    # Turnover-weighted: sum(pl) / sum(turnover), which is what the export's own
    # ROI column measures per row. The unweighted mean of that column is a
    # different number — small stakes are many and can pull it far from the
    # turnover-weighted figure — so averaging rows instead of weighting by
    # turnover is wrong, not merely imprecise.
    grouped["roi_pct"] = 100 * grouped["pl"] / grouped["turnover"]
    # Bets on one fixture win or lose together (CLAUDE.md rule 1), so this is
    # roughly the factor by which the slice's bet count overstates how much
    # independent information it carries.
    grouped["bets_per_fixture"] = grouped["bets"] / grouped["fixtures"]
    return grouped[
        ["slice", "bets", "fixtures", "bets_per_fixture", "turnover", "pl", "roi_pct"]
    ]


def sort_table(table: pd.DataFrame, sort: Sort) -> pd.DataFrame:
    return table.sort_values(sort.column, ascending=sort.ascending)


@dataclass(frozen=True)
class CurveRule:
    """What a slice needs before it gets its own cumulative curve.

    ``None`` means that bar does not apply. Every bar that does apply must be
    met, for the reason given at :data:`SMALL_MULTIPLE_MIN_TURNOVER`.
    """

    min_turnover: float
    min_bets: int | None = None
    min_fixtures: int | None = None


def history_curve_rule() -> CurveRule:
    """The bars for the four-year history. Read at call time, not import time."""
    return CurveRule(SMALL_MULTIPLE_MIN_TURNOVER, min_bets=SMALL_MULTIPLE_MIN_BETS)


def upload_curve_rule(frame: pd.DataFrame) -> CurveRule:
    """The bars for one uploaded file, scaled to its matched turnover."""
    turnover = float(frame["turnover"].sum())
    return CurveRule(
        round(UPLOAD_CURVE_MIN_TURNOVER_SHARE * turnover, 2),
        min_fixtures=UPLOAD_CURVE_MIN_FIXTURES,
    )


def eligible_for_curves(table_all: pd.DataFrame, rule: CurveRule) -> pd.DataFrame:
    """The slices big enough for a cumulative curve, largest first."""
    keep = table_all["turnover"] >= rule.min_turnover
    if rule.min_bets is not None:
        keep &= table_all["bets"] >= rule.min_bets
    if rule.min_fixtures is not None:
        keep &= table_all["fixtures"] >= rule.min_fixtures
    return table_all[keep].sort_values("turnover", ascending=False)


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------


class StakeRangeError(ValueError):
    """Raised when the stake filter is empty by construction."""


@dataclass(frozen=True)
class Filters:
    """What the explorer lets a person narrow the history down to.

    A missing date means no bound on that side. ``max_stake`` is compared to
    the ceiling before it is applied, so leaving it at the ceiling excludes
    nothing — and, unlike ``<= ceiling``, keeps rows whose stake is missing.
    """

    date_from: date | None = None
    date_to: date | None = None
    min_stake: float = 0.0
    max_stake: float | None = None
    market_types: tuple[str, ...] = field(default_factory=tuple)
    bookies: tuple[str, ...] = field(default_factory=tuple)


def stake_ceiling(frame: pd.DataFrame) -> float | None:
    """Whole units, at or above every stake, so a default filter excludes nothing.

    ``None`` when the export has no ``Stake`` column: there is nothing to filter on.
    """
    if "stake" not in frame.columns:
        return None
    return float(math.ceil(frame["stake"].max()))


def apply_filters(
    frame: pd.DataFrame, filters: Filters, ceiling: float | None
) -> pd.DataFrame:
    """Narrow a frame down. Stake bounds are ignored when there is no stake."""
    if "stake" in frame.columns and ceiling is not None:
        max_stake = ceiling if filters.max_stake is None else filters.max_stake
        if max_stake < filters.min_stake:
            raise StakeRangeError(
                f"Maximum stake ({max_stake:,.2f}) is below the minimum "
                f"({filters.min_stake:,.2f}) — no row can satisfy both."
            )
        if filters.min_stake:
            frame = frame[frame["stake"] >= filters.min_stake]
        if max_stake < ceiling:
            frame = frame[frame["stake"] <= max_stake]
    if filters.date_from is not None:
        frame = frame[frame["event_day"] >= pd.Timestamp(filters.date_from)]
    if filters.date_to is not None:
        frame = frame[frame["event_day"] <= pd.Timestamp(filters.date_to)]
    if filters.market_types and "market_type" in frame.columns:
        frame = frame[frame["market_type"].astype("string").isin(filters.market_types)]
    if filters.bookies and "bookie" in frame.columns:
        frame = frame[frame["bookie"].astype("string").isin(filters.bookies)]
    return frame


def option_values(frame: pd.DataFrame, column: str) -> list[str]:
    """Sorted distinct values for a multiselect. Missing values are not options."""
    return sorted(str(v) for v in frame[column].dropna().unique())


# --------------------------------------------------------------------------
# Over time
# --------------------------------------------------------------------------


def curve_freq(frame: pd.DataFrame) -> str:
    """``"D"`` for a frame spanning under a quarter, ``"M"`` otherwise.

    Decide it once on the unfiltered frame: a filter narrowing the dates should
    not flip the resolution of a chart the person is already reading.
    """
    span = frame["event_day"].max() - frame["event_day"].min()
    return "D" if span <= DAILY_BUCKET_MAX_SPAN else "M"


def by_period(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Turnover, P/L and running P/L per bucket, plus ``"day"`` or ``"month"``.

    Two labels per bucket: ``tick`` for the axis is the short one (a daily axis
    repeating the same year on every tick just collides with itself), ``label``
    for the tooltip the unambiguous one.
    """
    freq, fmt, tick_fmt, bucket = (
        ("D", "%d %b %Y", "%d %b", "day")
        if curve_freq(frame) == "D"
        else ("M", "%b %Y", "%b %Y", "month")
    )
    out = (
        frame.assign(period=frame["event_day"].dt.to_period(freq))
        .groupby("period", as_index=False)[["turnover", "pl"]]
        .sum()
    )
    out["period"] = out["period"].dt.to_timestamp()
    out["cumulative_pl"] = out["pl"].cumsum()
    out["label"] = out["period"].dt.strftime(fmt)
    out["tick"] = out["period"].dt.strftime(tick_fmt)
    return out, bucket


def cumulative_by_slice(
    frame: pd.DataFrame, columns: str | list[str], freq: str = "M"
) -> pd.DataFrame:
    """Running P/L and running ROI per slice and period, for the comparison chart.

    Monthly by default; ``freq="D"`` for a short upload, where months would
    leave one point per curve. The period column is called ``month`` either way.

    Running **ROI**, not only running P/L in currency: a large segment draws a
    tall P/L curve merely by being large, which compares size rather than
    skill. ``cumsum(pl) / cumsum(turnover)`` puts every segment on the same
    axis, and the shape carries the information — a real edge settles onto a
    positive number, noise keeps wandering.
    """
    monthly = (
        frame.assign(
            month=frame["event_day"].dt.to_period(freq),
            slice=slice_names(frame, columns),
        )
        .groupby(["slice", "month"])[["turnover", "pl"]]
        .sum()
        .reset_index()
    )
    monthly["month"] = monthly["month"].dt.to_timestamp()
    monthly = monthly.sort_values(["slice", "month"])
    grouped = monthly.groupby("slice")
    monthly["cum_pl"] = grouped["pl"].cumsum()
    monthly["cum_turnover"] = grouped["turnover"].cumsum()
    monthly["cum_roi_pct"] = 100 * monthly["cum_pl"] / monthly["cum_turnover"]
    return monthly
