"""Contract for odds.py. Fails until the owner implements it — that is the point.

Run with `pytest -m "not owner"` to skip while the module is unwritten.
"""

from __future__ import annotations

import pytest

import odds

pytestmark = pytest.mark.owner


def test_exact_ratio_gives_exact_odds():
    value, censored = odds.implied_odds(100.0, 85.0)
    assert censored is False
    assert value == pytest.approx(1.85)


def test_ratio_at_or_above_threshold_is_censored_and_returns_none():
    value, censored = odds.implied_odds(100.0, 100.0)
    assert censored is True
    assert value is None, "censored odds must never surface as the number 2.00"


def test_just_below_threshold_is_still_exact():
    value, censored = odds.implied_odds(100.0, 99.8)
    assert censored is False
    assert value == pytest.approx(1.998)


def test_missing_price_adjusted_turnover_is_unknown_not_zero():
    value, censored = odds.implied_odds(100.0, None)
    assert value is None
    assert censored is True


def test_censored_rows_have_nan_odds_in_the_frame(df):
    out = odds.add_implied_odds(df)
    assert out.loc[out["odds_censored"], "implied_odds"].isna().all()


def test_mean_of_implied_odds_cannot_be_dragged_to_two(df):
    out = odds.add_implied_odds(df)
    assert out["implied_odds"].max() < 2.0
