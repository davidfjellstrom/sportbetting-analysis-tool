"""Synthetic fixtures. No real export ever enters the test suite.

``synthetic_rows`` is small on purpose but covers the cases that have actually
caused bugs: an unmatched row, a both-sides pair, a multi-bet row, exact and
censored price-adjusted turnover, a pre-2025 row with the column missing, and a
novelty market.

The header mirrors a real export column for column, including order — which is
not the order CLAUDE.md once described. Two details matter and are easy to get
wrong from the documentation alone:

* ``Market`` is sport and period (``Football``, ``Football (Half Time)``), not
  the market description. It therefore does *not* separate a total from a
  handicap; only ``Market Type`` does. Test data that pretends otherwise makes
  ``POSITION_KEY`` look finer-grained than it is.
* ``Event Type`` is ``normal`` or ``multirunner``, not the sport.

``ROI`` is empty on unmatched rows in the real exports, and is empty here too.
Every populated ``ROI`` equals ``Customer P/L / Customer turnover`` exactly, as
``checks.check_roi_consistent`` requires.

Real pre-2025 exports carry the price-adjusted column but leave it blank. The
legacy fixture omits the column entirely instead, which is the stricter case:
a loader that survives an absent column certainly survives an empty one.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

RAW_HEADER = [
    "Event",
    "Market",
    "Market Type",
    "Selection",
    "Country",
    "Event Type",
    "Competition",
    "Bookie",
    "Event Day",
    "Customer currency",
    "Nr of Bets",
    "Stake",
    "Customer turnover",
    "Customer price adjusted turnover",
    "Customer P/L",
    "ROI",
]

# Event, Market, MarketType, Selection, Country, EventType, Competition, Bookie,
# EventDay, Currency, NrOfBets, Stake, Turnover, PAT, PL, ROI
RAW_ROWS: list[list] = [
    # Both sides of one total on one fixture -> both_sides_flag must be "both".
    ["Alpha v Beta", "Football", "ou", "over", "Spain", "normal", "La Liga",
     "pinnacle", "2025-03-01", "EUR", 1, 50.0, 50.0, 42.5, -50.0, -1.0],
    ["Alpha v Beta", "Football", "ou", "under", "Spain", "normal", "La Liga",
     "pinnacle", "2025-03-01", "EUR", 2, 60.0, 55.0, 47.0, 47.0,
     0.8545454545454545],
    # Same fixture and same Market, different Market Type -> must NOT trigger
    # both_sides_flag. Market alone cannot separate these; market_type must.
    ["Alpha v Beta", "Football", "ah", "home", "Spain", "normal", "La Liga",
     "betfair", "2025-03-01", "EUR", 1, 40.0, 40.0, 39.99, -40.0, -1.0],
    # Unmatched: turnover 0, ROI blank. Excluded from every performance figure.
    ["Gamma v Delta", "Football", "ou", "under", "Italy", "normal", "Serie A",
     "pinnacle", "2025-03-02", "EUR", 1, 30.0, 0.0, 0.0, 0.0, None],
    # Censored: ratio ~= 1 -> odds >= 2.00, value unknown.
    ["Gamma v Delta", "Football", "1x2", "away", "Italy", "normal", "Serie A",
     "cashout", "2025-03-02", "EUR", 3, 25.0, 25.0, 25.0, 63.0, 2.52],
    # Novelty market.
    ["Eps v Zeta", "Football", "cs", "home", "England", "normal", "Championship",
     "pinnacle", "2025-03-03", "EUR", 1, 20.0, 18.0, 9.0, -18.0, -1.0],
    # Same selection twice on one position -> n_bets_on_position >= 2.
    ["Eps v Zeta", "Football", "ou", "over", "England", "normal", "Championship",
     "pinnacle", "2025-03-03", "EUR", 2, 15.0, 15.0, 12.0, 12.0, 0.8],
    ["Eps v Zeta", "Football", "ou", "over", "England", "normal", "Championship",
     "betfair", "2025-03-03", "EUR", 1, 15.0, 15.0, 12.0, 12.0, 0.8],
]

# Pre-2025 export: identical schema minus the price-adjusted column.
LEGACY_ROWS: list[list] = [
    ["Eta v Theta", "Football", "ou", "under", "Sweden", "normal", "Allsvenskan",
     "pinnacle", "2023-07-14", "EUR", 4, 80.0, 72.0, None, 18.0, 0.25],
    ["Eta v Theta", "Football", "1x2", "draw", "Sweden", "normal", "Allsvenskan",
     "betfair", "2023-07-14", "EUR", 1, 10.0, 10.0, None, -10.0, -1.0],
]


def _write_csv(path: Path, rows: list[list], *, with_pat: bool) -> Path:
    header = (
        RAW_HEADER
        if with_pat
        else [c for c in RAW_HEADER if c != "Customer price adjusted turnover"]
    )
    idx = RAW_HEADER.index("Customer price adjusted turnover")
    body = rows if with_pat else [r[:idx] + r[idx + 1 :] for r in rows]
    pd.DataFrame(body, columns=header).to_csv(path, index=False)
    return path


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """A ``data/raw``-shaped directory: one modern export, one legacy export."""
    d = tmp_path / "raw"
    d.mkdir()
    _write_csv(d / "sportmarket_2025.csv", RAW_ROWS, with_pat=True)
    _write_csv(d / "sportmarket_2023.csv", LEGACY_ROWS, with_pat=False)
    return d


@pytest.fixture
def modern_csv(tmp_path: Path) -> Path:
    return _write_csv(tmp_path / "sportmarket_2025.csv", RAW_ROWS, with_pat=True)


@pytest.fixture
def df(raw_dir: Path) -> pd.DataFrame:
    """Fully loaded synthetic frame, unmatched rows still present."""
    import loader

    return loader.load_raw(raw_dir)
