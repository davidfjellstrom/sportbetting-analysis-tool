"""Contract for features.py — chiefly both_sides_flag, which is easy to get
subtly wrong and covers ~45% of lifetime turnover."""

from __future__ import annotations

import pytest

import features

pytestmark = pytest.mark.owner


def test_both_sides_flag_true_for_over_and_under_on_same_market(df):
    out = features.add_both_sides_flag(df)
    pair = out.loc[
        (out["event"] == "Alpha v Beta") & (out["market_type"] == "ou"),
        "both_sides_flag",
    ]
    assert pair.all()


def test_both_sides_flag_does_not_leak_across_markets(df):
    out = features.add_both_sides_flag(df)
    other = out.loc[
        (out["event"] == "Alpha v Beta") & (out["market_type"] == "ah"),
        "both_sides_flag",
    ]
    assert not other.any(), "home on one market is not 'both sides' of another"


def test_both_sides_flag_does_not_leak_across_fixtures(df):
    out = features.add_both_sides_flag(df)
    assert not out.loc[out["event"] == "Eps v Zeta", "both_sides_flag"].any()


def test_n_bets_on_position_counts_repeat_selections(df):
    out = features.add_n_bets_on_position(df)
    repeated = out.loc[
        (out["event"] == "Eps v Zeta") & (out["selection"] == "over"),
        "n_bets_on_position",
    ]
    assert (repeated >= 2).all()


def test_novelty_markets_flagged(df):
    out = features.add_is_novelty_market(df)
    assert out.loc[out["market_type"] == "cs", "is_novelty_market"].all()
    assert not out.loc[out["market_type"] == "ou", "is_novelty_market"].any()
