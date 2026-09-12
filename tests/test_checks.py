"""Contract for checks.py.

Two kinds of test here. The first kind pins the happy path: the synthetic
export is clean, so a full run must produce no errors. The second kind
corrupts one thing at a time and asserts the corresponding check notices —
because a check that cannot fail is decoration, not verification.
"""

from __future__ import annotations

import pandas as pd
import pytest

import checks
import loader

# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------


def test_clean_export_produces_no_errors(df):
    report = checks.run_checks(df)
    assert report.ok, [c.detail for c in report.errors]
    report.raise_if_errors()


def test_report_covers_every_check_and_is_printable(df):
    report = checks.run_checks(df)
    names = {c.name for c in report.checks}
    assert {
        "single_currency",
        "roi_consistent",
        "turnover_within_stake",
        "amounts_non_negative",
        "pat_within_turnover",
        "event_day_parsed",
        "dates_plausible",
        "no_duplicate_rows",
        "market_types_known",
        "unmatched_rows_carry_no_result",
    } <= names
    assert "checks:" in str(report)


def test_info_checks_never_fail(df):
    report = checks.run_checks(df)
    info = [c for c in report.checks if c.severity is checks.Severity.INFO]
    assert info, "coverage figures should be reported alongside the checks"
    assert all(c.passed for c in info)


# --------------------------------------------------------------------------
# Each check must be able to fail
# --------------------------------------------------------------------------


def test_mixed_currency_is_an_error(df):
    bad = df.copy()
    bad["currency"] = bad["currency"].astype("string")
    bad.loc[bad.index[0], "currency"] = "sek"
    check = checks.check_single_currency(bad)
    assert not check.passed
    assert check.severity is checks.Severity.ERROR
    assert "sek" in check.detail


def test_missing_currency_column_is_tolerated(df):
    check = checks.check_single_currency(df.drop(columns=["currency"]))
    assert check.passed
    assert check.severity is checks.Severity.INFO


def test_roi_that_disagrees_with_pl_over_turnover_is_an_error(df):
    bad = df.copy()
    matched = bad.index[bad["turnover"] > 0][0]
    bad.loc[matched, "roi"] = bad.loc[matched, "roi"] + 0.5
    check = checks.check_roi_consistent(bad)
    assert not check.passed
    assert check.severity is checks.Severity.ERROR


def test_roi_within_tolerance_still_passes(df):
    bad = df.copy()
    matched = bad.index[bad["turnover"] > 0][0]
    bad.loc[matched, "roi"] = bad.loc[matched, "roi"] + checks.ROI_TOLERANCE / 10
    assert checks.check_roi_consistent(bad).passed


def test_turnover_above_stake_is_an_error(df):
    bad = df.copy()
    bad.loc[bad.index[0], "turnover"] = bad.loc[bad.index[0], "stake"] + 1
    check = checks.check_turnover_within_stake(bad)
    assert not check.passed
    assert check.severity is checks.Severity.ERROR


def test_negative_stake_is_an_error(df):
    bad = df.copy()
    bad.loc[bad.index[0], "stake"] = -1.0
    assert not checks.check_amounts_non_negative(bad).passed


def test_zero_bets_on_a_row_is_an_error(df):
    bad = df.copy()
    bad.loc[bad.index[0], "n_bets"] = 0
    assert not checks.check_amounts_non_negative(bad).passed


def test_price_adjusted_turnover_above_the_bound_is_an_error(df):
    bad = df.copy()
    row = bad.index[bad["price_adjusted_turnover"].notna() & (bad["turnover"] > 0)][0]
    bad.loc[row, "price_adjusted_turnover"] = bad.loc[row, "turnover"] * 2
    check = checks.check_pat_within_turnover(bad)
    assert not check.passed
    assert check.severity is checks.Severity.ERROR


def test_observed_censoring_ceiling_still_passes(df):
    """The real data reaches ratio 1.0227; that must not trip the check."""
    bad = df.copy()
    row = bad.index[bad["price_adjusted_turnover"].notna() & (bad["turnover"] > 0)][0]
    bad.loc[row, "price_adjusted_turnover"] = bad.loc[row, "turnover"] * 1.0227
    assert checks.check_pat_within_turnover(bad).passed


def test_unparseable_date_is_an_error(df):
    bad = df.copy()
    bad.loc[bad.index[0], "event_day"] = pd.NaT
    check = checks.check_event_day_parsed(bad)
    assert not check.passed
    assert check.severity is checks.Severity.ERROR


def test_implausible_date_is_a_warning(df):
    bad = df.copy()
    bad.loc[bad.index[0], "event_day"] = pd.Timestamp("1999-01-01")
    check = checks.check_dates_plausible(bad)
    assert not check.passed
    assert check.severity is checks.Severity.WARN


def test_duplicate_row_is_a_warning(df):
    bad = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    check = checks.check_no_duplicate_rows(bad)
    assert not check.passed
    assert check.severity is checks.Severity.WARN


def test_duplicate_across_source_files_is_still_caught(df):
    """``source_file`` is excluded from the comparison on purpose."""
    dupe = df.iloc[[0]].copy()
    dupe["source_file"] = "sportmarket_9999.csv"
    assert not checks.check_no_duplicate_rows(
        pd.concat([df, dupe], ignore_index=True)
    ).passed


def test_unrecognised_market_type_is_a_warning(df):
    bad = df.copy()
    bad["market_type"] = bad["market_type"].astype("string")
    bad.loc[bad.index[0], "market_type"] = "teleport"
    check = checks.check_market_types_known(bad)
    assert not check.passed
    assert check.severity is checks.Severity.WARN
    assert "teleport" in check.detail


def test_unmatched_row_carrying_pl_is_a_warning_and_reports_the_amount(df):
    bad = df.copy()
    row = bad.index[bad["turnover"] <= 0][0]
    bad.loc[row, "pl"] = 32.23
    check = checks.check_unmatched_rows_carry_no_result(bad)
    assert not check.passed
    assert check.severity is checks.Severity.WARN
    assert "32.23" in check.detail


# --------------------------------------------------------------------------
# Report behaviour
# --------------------------------------------------------------------------


def test_warnings_do_not_raise(df):
    bad = df.copy()
    row = bad.index[bad["turnover"] <= 0][0]
    bad.loc[row, "pl"] = 1.0
    report = checks.run_checks(bad)
    assert report.warnings
    assert report.ok
    report.raise_if_errors()


def test_errors_raise_with_a_useful_message(df):
    bad = df.copy()
    bad["currency"] = bad["currency"].astype("string")
    bad.loc[bad.index[0], "currency"] = "gbp"
    report = checks.run_checks(bad)
    assert not report.ok
    with pytest.raises(checks.IntegrityError, match="single_currency"):
        report.raise_if_errors()


def test_battery_runs_on_a_freshly_loaded_frame(raw_dir):
    """End to end: load the synthetic exports, then check them."""
    report = checks.run_checks(loader.load_raw(raw_dir))
    assert report.ok
