"""Loader tests. These must pass on a fresh clone."""

from __future__ import annotations

import pandas as pd
import pytest

import loader


def test_columns_are_normalised(modern_csv):
    df = loader.load_file(modern_csv)
    for col in loader.REQUIRED_COLUMNS:
        assert col in df.columns
    assert "price_adjusted_turnover" in df.columns
    assert "Customer P/L" not in df.columns


def test_missing_required_column_raises(tmp_path):
    path = tmp_path / "broken.csv"
    pd.DataFrame({"Event": ["A v B"], "Stake": [1.0]}).to_csv(path, index=False)
    with pytest.raises(loader.SchemaError):
        loader.load_file(path)


def test_legacy_export_gets_pat_column_as_missing_not_zero(raw_dir):
    df = loader.load_raw(raw_dir)
    legacy = df.loc[df["source_file"] == "sportmarket_2023.csv"]
    assert len(legacy) == 2
    assert legacy["price_adjusted_turnover"].isna().all()
    assert not (legacy["price_adjusted_turnover"].fillna(-1) == 0).any()


def test_fixture_id_is_event_plus_day(df):
    same_day = df.loc[df["event"] == "Alpha v Beta", "fixture_id"].unique()
    assert len(same_day) == 1
    assert df["fixture_id"].nunique() == 4


def test_matched_drops_zero_turnover_rows(df):
    m = loader.matched(df)
    assert (m["turnover"] > 0).all()
    assert len(m) == len(df) - 1
    assert len(loader.unmatched(df)) == 1


def test_matched_and_unmatched_partition_the_frame(df):
    assert len(loader.matched(df)) + len(loader.unmatched(df)) == len(df)


def test_fill_rate_is_turnover_over_stake(df):
    assert loader.fill_rate(df) == pytest.approx(
        df["turnover"].sum() / df["stake"].sum()
    )


def test_period_slices_inclusively(df):
    assert len(loader.period(df, "2025-03-02", "2025-03-02")) == 2
    assert len(loader.period(df, end="2023-12-31")) == 2


def test_describe_counts_bets_not_rows(df):
    report = loader.describe(df)
    assert report.n_rows == len(df)
    assert report.n_bets == int(df["n_bets"].sum())
    assert report.n_bets > report.n_rows
    assert report.n_fixtures == 4
    assert report.n_unmatched_rows == 1


def test_empty_raw_dir_raises_with_a_useful_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="gitignored"):
        loader.load_raw(tmp_path)
