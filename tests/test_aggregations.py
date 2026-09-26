"""aggregations.py: the figures the app shows, on synthetic data only."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import aggregations as agg
import loader


@pytest.fixture
def matched(df: pd.DataFrame) -> pd.DataFrame:
    return loader.matched(df)


@pytest.fixture
def with_missing_side(matched: pd.DataFrame) -> pd.DataFrame:
    """The synthetic rows all carry a side; blank two so absence has to be handled."""
    out = matched.copy()
    idx = out.index[:2]
    out.loc[idx, "selection"] = pd.NA
    return out


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------


def test_dimensions_are_twelve_in_fixed_order():
    assert [d.key for d in agg.DIMENSIONS] == [
        "market_type", "selection", "bookie", "country", "competition", "market",
        "event_type", "position_size", "n_bets_bucket", "year", "month", "weekday",
    ]


def test_sorts_have_unique_keys_and_labels():
    assert len({s.key for s in agg.SORTS}) == len(agg.SORTS) == 7
    assert len({s.label for s in agg.SORTS}) == len(agg.SORTS)
    assert agg.SORT_BY_KEY["roi_asc"].ascending is True
    assert agg.SORT_BY_KEY["name_asc"].column == "slice"


# --------------------------------------------------------------------------
# currency_code
# --------------------------------------------------------------------------


def test_currency_code_reads_the_column(matched):
    assert agg.currency_code(matched) == "EUR"
    assert agg.currency_code(loader.to_units(matched, 10.0)) == "units"
    assert agg.currency_code(matched.drop(columns=["currency"])) == "EUR"


# --------------------------------------------------------------------------
# with_dimensions
# --------------------------------------------------------------------------


def test_position_size_edges_are_left_closed():
    frame = pd.DataFrame(
        {
            "event_day": pd.to_datetime(["2025-03-01"] * 5),
            "turnover": [0.49, 0.5, 1.0, 10.0, float("nan")],
            "n_bets": [1, 1, 1, 1, 1],
        }
    )
    out = agg.with_dimensions(frame)
    assert list(out["_position_size"].astype("string").fillna("?")) == [
        "<0.5 u", "0.5-1 u", "1-2 u", "10+ u", "?",
    ]


def test_position_size_is_the_row_matched_in_units():
    """With 1 unit = 10 EUR: one bet matched for 20 EUR is 2 u; three bets
    matched for 60 EUR together are one 6 u position; a 50 EUR stake of which
    only 12 EUR matched is 1.2 u, because what matched is what was played."""
    frame = pd.DataFrame(
        {
            "event_day": pd.to_datetime(["2025-03-01"] * 3),
            "stake": [20.0, 60.0, 50.0],
            "turnover": [20.0, 60.0, 12.0],
            "n_bets": [1, 3, 1],
        }
    )
    out = agg.with_dimensions(frame, unit=10.0)
    assert list(out["_position_size"].astype("string")) == ["2-3 u", "5-10 u", "1-2 u"]


def test_n_bets_bucket():
    frame = pd.DataFrame(
        {
            "event_day": pd.to_datetime(["2025-03-01"] * 5),
            "turnover": [1.0] * 5,
            "n_bets": [1, 2, 3, 7, 1],
        }
    )
    out = agg.with_dimensions(frame)
    assert list(out["_n_bets_bucket"].astype("string")) == ["1", "2", "3+", "3+", "1"]


def test_calendar_dimensions_are_strings(matched):
    out = agg.with_dimensions(matched)
    row = out.iloc[0]
    assert row["_year"] == "2023"
    assert row["_month"] == "2023-07"
    assert row["_weekday"] == "Friday"
    assert out.shape[0] == matched.shape[0]


def test_with_dimensions_does_not_touch_the_input(matched):
    before = list(matched.columns)
    agg.with_dimensions(matched)
    assert list(matched.columns) == before


# --------------------------------------------------------------------------
# aggregate
# --------------------------------------------------------------------------


def test_aggregate_columns_and_totals(matched):
    table = agg.aggregate(matched, "market_type")
    assert list(table.columns) == [
        "slice", "bets", "fixtures", "bets_per_fixture", "turnover", "pl", "roi_pct",
    ]
    assert table["turnover"].sum() == pytest.approx(matched["turnover"].sum())
    assert table["pl"].sum() == pytest.approx(matched["pl"].sum())
    assert table["bets"].sum() == matched["n_bets"].sum()


def test_roi_is_turnover_weighted_not_row_mean(matched):
    ou = matched[matched["market_type"] == "ou"]
    table = agg.aggregate(matched, "market_type").set_index("slice")
    weighted = 100 * ou["pl"].sum() / ou["turnover"].sum()
    row_mean = 100 * ou["roi"].mean()
    assert table.loc["ou", "roi_pct"] == pytest.approx(weighted)
    assert weighted != pytest.approx(row_mean)


def test_bets_per_fixture(matched):
    table = agg.aggregate(matched, "market_type").set_index("slice")
    ou = matched[matched["market_type"] == "ou"]
    assert table.loc["ou", "fixtures"] == ou["fixture_id"].nunique()
    assert table.loc["ou", "bets_per_fixture"] == pytest.approx(
        ou["n_bets"].sum() / ou["fixture_id"].nunique()
    )


def test_missing_side_is_its_own_slice_not_dropped(with_missing_side):
    table = agg.aggregate(with_missing_side, "selection")
    assert "(no value)" in set(table["slice"])
    assert table["turnover"].sum() == pytest.approx(with_missing_side["turnover"].sum())
    blank = with_missing_side[with_missing_side["selection"].isna()]
    assert table.set_index("slice").loc["(no value)", "turnover"] == pytest.approx(
        blank["turnover"].sum()
    )


def test_sort_table(matched):
    table = agg.aggregate(matched, "bookie")
    best = agg.sort_table(table, agg.SORT_BY_KEY["roi_desc"])
    assert list(best["roi_pct"]) == sorted(best["roi_pct"], reverse=True)
    by_name = agg.sort_table(table, agg.SORT_BY_KEY["name_asc"])
    assert list(by_name["slice"]) == sorted(by_name["slice"])


def test_eligible_for_curves_needs_both_thresholds():
    table = pd.DataFrame(
        {
            "slice": ["big", "rich-but-few", "many-but-poor", "small"],
            "bets": [2_000, 10, 5_000, 5],
            "fixtures": [1, 1, 1, 1],
            "bets_per_fixture": [1.0] * 4,
            "turnover": [350.0, 10_000.0, 100.0, 1.0],
            "pl": [0.0] * 4,
            "roi_pct": [0.0] * 4,
        }
    )
    rule = agg.history_curve_rule()
    assert list(agg.eligible_for_curves(table, rule)["slice"]) == ["big"]


# --------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------


def test_stake_ceiling_is_a_whole_number_at_or_above_the_max(matched):
    ceiling = agg.stake_ceiling(matched)
    assert ceiling >= matched["stake"].max()
    assert ceiling == int(ceiling)


def test_default_filters_exclude_nothing(matched):
    out = agg.apply_filters(matched, agg.Filters(), agg.stake_ceiling(matched))
    assert len(out) == len(matched)


def test_max_at_ceiling_keeps_rows_with_a_missing_stake(matched):
    frame = matched.copy()
    frame.loc[frame.index[0], "stake"] = float("nan")
    ceiling = agg.stake_ceiling(frame)
    kept = agg.apply_filters(frame, agg.Filters(max_stake=ceiling), ceiling)
    assert len(kept) == len(frame)
    below = agg.apply_filters(frame, agg.Filters(max_stake=ceiling - 1), ceiling)
    assert len(below) == len(frame) - 1 - int((frame["stake"] > ceiling - 1).sum())


def test_stake_range_error_message(matched):
    with pytest.raises(agg.StakeRangeError) as exc:
        agg.apply_filters(matched, agg.Filters(min_stake=5, max_stake=2), 100.0)
    assert str(exc.value) == (
        "Maximum stake (2.00) is below the minimum (5.00) — no row can satisfy both."
    )


def test_filters_dates_stakes_types_bookies(matched):
    ceiling = agg.stake_ceiling(matched)
    dated = agg.apply_filters(
        matched,
        agg.Filters(date_from=date(2025, 3, 2), date_to=date(2025, 3, 2)),
        ceiling,
    )
    assert set(dated["event_day"].dt.date) == {date(2025, 3, 2)}

    staked = agg.apply_filters(matched, agg.Filters(min_stake=40, max_stake=60), ceiling)
    assert staked["stake"].between(40, 60).all()
    assert len(staked) == int(matched["stake"].between(40, 60).sum())

    picked = agg.apply_filters(
        matched, agg.Filters(market_types=("ou",), bookies=("pinnacle",)), ceiling
    )
    assert set(picked["market_type"].astype("string")) == {"ou"}
    assert set(picked["bookie"].astype("string")) == {"pinnacle"}


def test_option_values_are_sorted_strings_without_missing(with_missing_side):
    values = agg.option_values(with_missing_side, "selection")
    assert values == sorted(values)
    assert "" not in values
    assert all(isinstance(v, str) for v in values)


# --------------------------------------------------------------------------
# over time
# --------------------------------------------------------------------------


def test_by_period_months_over_a_long_span(matched):
    table, bucket = agg.by_period(matched)
    assert bucket == "month"
    assert list(table["cumulative_pl"]) == pytest.approx(list(table["pl"].cumsum()))
    assert table["turnover"].sum() == pytest.approx(matched["turnover"].sum())


def test_by_period_days_over_a_short_span(matched):
    short = matched[matched["event_day"] >= "2025-01-01"]
    table, bucket = agg.by_period(short)
    assert bucket == "day"
    assert len(table) == short["event_day"].dt.normalize().nunique()
    assert table["label"].iloc[0] == "01 Mar 2025"
    assert table["tick"].iloc[0] == "01 Mar"


def test_by_period_survives_an_empty_frame(matched):
    table, bucket = agg.by_period(matched.iloc[0:0])
    assert table.empty
    assert bucket == "month"


def test_cumulative_by_slice(with_missing_side):
    curves = agg.cumulative_by_slice(with_missing_side, "selection")
    assert "(no value)" in set(curves["slice"])
    for _, part in curves.groupby("slice", observed=True):
        assert list(part["month"]) == sorted(part["month"])
        assert list(part["cum_pl"]) == pytest.approx(list(part["pl"].cumsum()))
        assert list(part["cum_roi_pct"]) == pytest.approx(
            list(100 * part["pl"].cumsum() / part["turnover"].cumsum())
        )


# --------------------------------------------------------------------------
# Uploads with columns left out
# --------------------------------------------------------------------------


def _upload(path):
    with path.open("rb") as fh:
        return loader.load_upload(fh, path.name)


def test_every_dimension_available_on_a_full_export(matched):
    assert agg.available_dimensions(agg.with_dimensions(matched)) == agg.DIMENSIONS


def test_dimension_without_its_column_is_not_available(export_without):
    frame = agg.with_dimensions(_upload(export_without("Bookie", "Stake")))
    keys = {d.key for d in agg.available_dimensions(frame)}
    assert "bookie" not in keys
    # Position size is cut on turnover, which every export carries.
    assert {"country", "n_bets_bucket", "position_size", "year"} <= keys


def test_aggregate_without_n_bets_leaves_bets_unknown(export_without):
    frame = loader.matched(_upload(export_without("Nr of Bets")))
    table = agg.aggregate(frame, "market_type")
    assert table["bets"].isna().all()
    assert table["bets_per_fixture"].isna().all()
    assert (table["fixtures"] >= 1).all()
    assert table["turnover"].sum() == pytest.approx(frame["turnover"].sum())


def test_upload_curve_rule_scales_with_the_file(matched):
    rule = agg.upload_curve_rule(matched)
    share = agg.UPLOAD_CURVE_MIN_TURNOVER_SHARE
    assert rule.min_turnover == pytest.approx(share * matched["turnover"].sum(), abs=0.01)
    assert rule.min_bets is None
    assert rule.min_fixtures == agg.UPLOAD_CURVE_MIN_FIXTURES


def test_eligible_for_curves_can_bar_on_matches():
    table = pd.DataFrame(
        {"slice": ["wide", "narrow"], "bets": [float("nan")] * 2,
         "fixtures": [30, 5], "turnover": [100.0, 100.0]}
    )
    rule = agg.CurveRule(min_turnover=50.0, min_fixtures=20)
    assert list(agg.eligible_for_curves(table, rule)["slice"]) == ["wide"]


def test_curve_freq_is_daily_for_a_short_span(matched):
    short = matched[matched["event_day"] >= "2025-01-01"]
    assert agg.curve_freq(short) == "D"
    assert agg.curve_freq(matched) == "M"
