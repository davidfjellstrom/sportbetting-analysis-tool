"""Implied odds recovered from price-adjusted turnover, with censoring.

    OWNER MODULE — see CLAUDE.md -> Division of labour.
    Scaffolding only: signatures, the contract, and the reason it matters.
    The implementations are deliberately left to the repo owner.

The derivation (reverse-engineered, the most fragile domain knowledge here)::

    price_adjusted_turnover = turnover * min(1, odds - 1)

so with ``ratio = price_adjusted_turnover / turnover``:

* ``ratio < 0.999``  -> ``odds = 1 + ratio``, exact.
* ``ratio >= 0.999`` -> odds were >= 2.00 and the true value is **unknown**.
  This is right-censoring, not a value of 2.00.

The price-adjusted column is only populated in later years, so coverage is
conditional: report it within the populated years and across the whole
dataset separately. Losing bets are covered too, not only winners.

The non-negotiable rule: a censored odds value must never be used as the point
estimate 2.00 — not in a mean, not as a bucket boundary, not as a regression
feature. The API below is shaped so that getting this wrong requires effort:
the caller is handed ``None`` plus a flag and has to decide.

Anything that cannot handle censored input should raise, not coerce.
"""

from __future__ import annotations

CENSOR_RATIO_THRESHOLD: float = 0.999
"""Ratios at or above this are censored: odds were >= 2.00, value unknown."""


def implied_odds(
    turnover: float,
    price_adjusted_turnover: float | None,
) -> tuple[float | None, bool]:
    """Recover decimal odds from a row's turnover pair.

    Returns:
        ``(odds, is_censored)``. When ``is_censored`` is True, ``odds`` is
        ``None`` and the caller must handle the ">= 2.00, unknown" case
        explicitly. When ``price_adjusted_turnover`` is missing (pre-2025
        rows) the result is ``(None, True)``: unknown is unknown.
    """
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def add_implied_odds(df):
    """Vectorised counterpart: attach ``implied_odds`` and ``odds_censored``.

    ``implied_odds`` must be NaN wherever ``odds_censored`` is True, so that a
    careless ``.mean()`` drops censored rows rather than silently pulling the
    average toward 2.00.
    """
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def odds_bucket(odds: float | None, is_censored: bool) -> str:
    """Label a row for grouped analysis.

    Censored rows form their own bucket (e.g. ``">=2.00"``); they may never be
    merged into a finite bucket whose boundary they might not respect.
    """
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")
