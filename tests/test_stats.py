"""Contract for stats.py: nothing leaves this module without an interval, and
nothing resamples rows."""

from __future__ import annotations

import pytest

import loader
import stats

pytestmark = pytest.mark.owner


def test_yield_never_returns_a_bare_number(df):
    est = stats.yield_with_ci(loader.matched(df))
    assert hasattr(est, "ci_low") and hasattr(est, "ci_high")
    assert est.ci_low <= est.value <= est.ci_high


def test_estimate_reports_fixture_count_not_only_rows(df):
    est = stats.yield_with_ci(loader.matched(df))
    assert est.n_fixtures <= est.n_rows
    assert est.n_fixtures == loader.matched(df)["fixture_id"].nunique()


def test_bootstrap_resamples_whole_fixtures(df):
    """A fixture must appear all-or-nothing in a resample, never split by row."""
    seen = []
    stats.clustered_bootstrap(
        loader.matched(df), statistic=lambda d: seen.append(d) or 0.0, n_boot=5
    )
    for sample in seen:
        for fixture, rows in sample.groupby("fixture_id"):
            expected = len(df.loc[df["fixture_id"] == fixture])
            assert len(rows) % expected == 0


def test_tiny_slice_is_reported_as_inadequate(df):
    est = stats.yield_with_ci(loader.matched(df))
    assert est.adequate is False, "8 synthetic rows cannot resolve a 4% effect"
