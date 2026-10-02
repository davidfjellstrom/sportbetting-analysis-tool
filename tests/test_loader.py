"""Loader tests. These must pass on a fresh clone."""

from __future__ import annotations

import io

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


def test_to_units_scales_money_only_and_relabels_currency(df):
    out = loader.to_units(df, 10.0)
    for col in loader.MONEY_COLUMNS:
        pd.testing.assert_series_equal(out[col], df[col] / 10.0, check_names=False)
    assert out["roi"].equals(df["roi"])
    assert out["n_bets"].equals(df["n_bets"])
    assert set(out["currency"].dropna().unique()) == {"units"}


def test_to_units_rejects_non_positive_unit(df):
    with pytest.raises(ValueError):
        loader.to_units(df, 0)


def test_write_units_output_reloads_through_the_same_pipeline(raw_dir, tmp_path):
    out_dir = tmp_path / "processed"
    unit = loader.write_units(raw_dir, out_dir)
    raw = loader.load_raw(raw_dir)
    assert unit == loader.typical_stake(raw)

    proc = loader.load_raw(out_dir)
    assert len(proc) == len(raw)
    assert set(proc["currency"].dropna().unique()) == {"units"}
    # Scale-invariant quantities survive untouched; money is divided by unit.
    assert proc["roi"].equals(raw["roi"])
    assert proc["fixture_id"].equals(raw["fixture_id"])
    assert loader.fill_rate(proc) == pytest.approx(loader.fill_rate(raw))
    pd.testing.assert_series_equal(
        proc["turnover"], raw["turnover"] / unit, check_names=False
    )
    # Absent stays absent: the legacy file has no price-adjusted column.
    assert proc["price_adjusted_turnover"].isna().sum() == (
        raw["price_adjusted_turnover"].isna().sum()
    )
    # The unit is nowhere in the output.
    for path in out_dir.glob("*.csv"):
        assert f"{unit}" not in path.read_text()


# --------------------------------------------------------------------------
# Uploads: only four columns required, the rest optional
# --------------------------------------------------------------------------


def _upload(path):
    with path.open("rb") as fh:
        return loader.load_upload(fh, path.name)


def test_upload_needs_only_fixture_and_result_columns(export_without):
    from conftest import RAW_HEADER, UPLOAD_REQUIRED_HEADERS

    optional = [h for h in RAW_HEADER if h not in UPLOAD_REQUIRED_HEADERS]
    df = _upload(export_without(*optional))
    assert set(loader.UPLOAD_REQUIRED_COLUMNS) <= set(df.columns)
    assert df["fixture_id"].nunique() == 3


@pytest.mark.parametrize(
    "header", ["Event", "Event Day", "Customer turnover", "Customer P/L"]
)
def test_upload_without_a_required_column_raises_naming_it(export_without, header):
    with pytest.raises(loader.SchemaError, match=f"\\['{header}'\\]"):
        _upload(export_without(header))


def test_absent_optional_column_stays_absent_not_nan(export_without):
    df = _upload(export_without("Bookie", "Selection"))
    assert "bookie" not in df.columns
    assert "selection" not in df.columns
    assert loader.missing_columns(df) == ("Selection", "Bookie")


def test_full_export_misses_nothing(modern_csv):
    assert loader.missing_columns(loader.load_file(modern_csv)) == ()


def test_history_still_requires_every_column(export_without):
    with pytest.raises(loader.SchemaError, match="Bookie"):
        loader.load_file(export_without("Bookie"))


def test_describe_without_n_bets_reports_bets_as_unknown(export_without):
    report = loader.describe(_upload(export_without("Nr of Bets")))
    assert report.n_bets is None
    assert "unknown bets" in str(report)


def test_fill_rate_without_stake_is_nan(export_without):
    assert pd.isna(loader.fill_rate(_upload(export_without("Stake"))))


def test_in_currency_scales_money_only_and_relabels(df):
    out = loader.in_currency(df, 11.0, "SEK")
    for col in loader.MONEY_COLUMNS:
        assert out[col].sum() == pytest.approx(11.0 * df[col].sum())
    assert out["roi"].equals(df["roi"])
    assert out["n_bets"].equals(df["n_bets"])
    assert set(out["currency"]) == {"sek"}


def test_in_currency_rejects_non_positive_rate(df):
    with pytest.raises(ValueError):
        loader.in_currency(df, 0, "SEK")


# --------------------------------------------------------------------------
# Files resaved by a spreadsheet. Excel in a decimal-comma locale (Swedish,
# German, …) saves semicolons and decimal commas, and plain "CSV" on Windows
# is cp1252, not UTF-8. Each must load to exactly the frame the original does.
# --------------------------------------------------------------------------

MONEY_HEADERS = (
    "Stake",
    "Customer turnover",
    "Customer price adjusted turnover",
    "Customer P/L",
    "ROI",
)


def _resaved(modern_csv, *, sep: str, decimal: str, encoding: str) -> bytes:
    table = pd.read_csv(modern_csv, dtype=str, keep_default_na=False)
    table.loc[0, "Event"] = "Malmö FF v Häcken"  # not ASCII, so encoding matters
    if decimal == ",":
        for col in MONEY_HEADERS:
            table[col] = table[col].str.replace(".", ",", regex=False)
    return table.to_csv(index=False, sep=sep).encode(encoding)


@pytest.mark.parametrize(
    ("sep", "decimal", "encoding"),
    [
        (",", ".", "utf-8-sig"),  # the original with a byte-order mark
        (";", ",", "utf-8-sig"),  # Excel, "CSV UTF-8"
        (";", ",", "cp1252"),  # Excel on Windows, plain "CSV"
        (";", ".", "utf-8"),  # semicolons, decimal point
        ("\t", ".", "utf-8"),  # tab-separated
    ],
)
def test_resaved_export_loads_like_the_original(modern_csv, sep, decimal, encoding):
    original = loader.load_upload(
        io.BytesIO(_resaved(modern_csv, sep=",", decimal=".", encoding="utf-8")),
        "x.csv",
    )
    resaved = loader.load_upload(
        io.BytesIO(_resaved(modern_csv, sep=sep, decimal=decimal, encoding=encoding)),
        "x.csv",
    )
    pd.testing.assert_frame_equal(resaved, original)
    assert resaved.loc[0, "event"] == "Malmö FF v Häcken"


def test_read_export_reports_the_format_it_found(modern_csv):
    payload = _resaved(modern_csv, sep=";", decimal=",", encoding="cp1252")
    _, fmt = loader.read_export(payload, "x.csv")
    assert fmt == loader.CsvFormat(encoding="cp1252", delimiter=";", decimal=",")


def test_comma_in_a_text_column_is_not_a_decimal_comma(modern_csv):
    # A semicolon file whose amounts use points: "1,5" may appear in text
    # (an event name), but that must not flip the decimal mark.
    table = pd.read_csv(modern_csv, dtype=str, keep_default_na=False)
    table.loc[0, "Event"] = "Team 1,5 v Team 2"
    _, fmt = loader.read_export(table.to_csv(index=False, sep=";").encode(), "x.csv")
    assert fmt.decimal == "."


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "empty"),
        (b"   \n\n", "empty"),
        (b'Event,Event Day\n"unterminated', "does not read as a CSV table"),
    ],
)
def test_unreadable_upload_raises_a_message_for_people(payload, message):
    with pytest.raises(loader.SchemaError, match=message):
        loader.load_upload(io.BytesIO(payload), "x.csv")
