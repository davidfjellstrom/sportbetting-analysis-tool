"""The API over the synthetic fixtures. No real export ever enters here.

The history dependency is overridden with the synthetic frame, so no test
touches ``data/processed/``; a machine without it runs the same suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import aggregations as agg
import loader
from api import fx
from api.history import History, get_history
from api.index import app
from conftest import RAW_HEADER, UPLOAD_REQUIRED_HEADERS


def _reject_nan(value: str):  # pragma: no cover - only called on bad output
    raise AssertionError(f"non-finite number in JSON: {value}")


def strict_json(response) -> dict:
    """``response.json()`` would happily accept ``NaN``; a browser will not."""
    assert response.status_code == 200, response.text
    return json.loads(response.text, parse_constant=_reject_nan)


@pytest.fixture
def client(df: pd.DataFrame):
    app.dependency_overrides[get_history] = lambda: History.from_frame(df)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def bare_client():
    """No override: the real loader path, pointed at a directory with no files."""
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------
# Overview and options
# --------------------------------------------------------------------------


def test_overview_matches_loader(client, df):
    body = strict_json(client.get("/api/overview"))
    matched = loader.matched(df)
    report = loader.describe(df)
    assert body["currency"] == "EUR"
    assert body["matched"]["turnover"] == pytest.approx(matched["turnover"].sum())
    assert body["matched"]["pl"] == pytest.approx(matched["pl"].sum())
    assert body["fill_rate"] == pytest.approx(loader.fill_rate(df))
    assert body["report"]["n_rows"] == report.n_rows
    assert body["report"]["n_bets"] == report.n_bets
    assert body["report"]["n_fixtures"] == report.n_fixtures
    assert body["report"]["n_unmatched_rows"] == report.n_unmatched_rows
    assert body["report"]["date_min"] == "2023-07-14"
    assert body["report"]["price_adjusted_coverage"] == pytest.approx(
        report.price_adjusted_coverage
    )


def test_overview_carries_the_check_report(client):
    body = strict_json(client.get("/api/overview"))
    checks = body["checks"]
    assert checks["ok"] is True
    assert {c["severity"] for c in checks["checks"]} == {"ERROR", "WARN", "INFO"}
    assert checks["n_errors"] == 0
    assert checks["n_warnings"] == len(
        [c for c in checks["checks"] if not c["passed"] and c["severity"] == "WARN"]
    )


def test_overview_series_is_monthly_and_cumulative(client, df):
    body = strict_json(client.get("/api/overview"))
    series = body["cumulative"]
    assert series["bucket"] == "month"
    pls = [p["pl"] for p in series["points"]]
    cum = [p["cumulative_pl"] for p in series["points"]]
    assert cum == pytest.approx(list(pd.Series(pls).cumsum()))
    assert series["points"][0]["label"] == "Jul 2023"
    assert series["points"][0]["tick"] == "Jul 2023"


def test_history_responses_are_cdn_cacheable(client):
    for path in ("/api/overview", "/api/explore/options", "/api/explore"):
        response = client.get(path)
        assert response.status_code == 200
        assert "s-maxage" in response.headers["cache-control"]


def test_explore_options(client, df):
    body = strict_json(client.get("/api/explore/options"))
    assert body["date_min"] == "2023-07-14"
    assert body["date_max"] == "2025-03-03"
    assert body["stake_ceiling"] == 80
    assert body["market_types"] == ["1x2", "ah", "cs", "ou"]
    assert body["bookies"] == ["betfair", "cashout", "pinnacle"]
    assert [d["key"] for d in body["dimensions"]] == [d.key for d in agg.DIMENSIONS]
    assert [s["key"] for s in body["sorts"]] == [s.key for s in agg.SORTS]
    assert body["compare"] == {
        "min_turnover": 350.0, "min_bets": 2000, "min_fixtures": None, "max_series": 8
    }


def test_no_processed_data_is_a_clear_503(bare_client, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(loader, "DEFAULT_PROCESSED_DIR", tmp_path)
    from api import history

    history.load_history.cache_clear()
    response = bare_client.get("/api/overview")
    assert response.status_code == 503
    assert "python src/loader.py" in response.json()["detail"]


# --------------------------------------------------------------------------
# Explore
# --------------------------------------------------------------------------


def test_explore_default_view_matches_aggregations(client, df):
    body = strict_json(client.get("/api/explore"))
    matched = loader.matched(df)
    table = agg.aggregate(agg.with_dimensions(matched), "market_type")
    assert body["status"] == "ok"
    assert body["view"]["turnover"] == pytest.approx(matched["turnover"].sum())
    assert body["view"]["roi_pct"] == pytest.approx(
        100 * matched["pl"].sum() / matched["turnover"].sum()
    )
    assert body["view"]["bets"] == int(matched["n_bets"].sum())
    assert body["groups_shown"] == body["groups_total"] == len(table)
    by_slice = {row["slice"]: row for row in body["table"]}
    for row in table.itertuples(index=False):
        assert by_slice[row.slice]["roi_pct"] == pytest.approx(row.roi_pct)
        assert by_slice[row.slice]["bets_per_fixture"] == pytest.approx(
            row.bets_per_fixture
        )
    turnovers = [by_slice[s]["turnover"] for s in body["bars_order"]]
    assert turnovers == sorted(turnovers, reverse=True)


def test_explore_sort_and_threshold(client):
    body = strict_json(
        client.get("/api/explore", params={"sort": "roi_asc", "min_fixtures": 2})
    )
    rois = [row["roi_pct"] for row in body["table"]]
    assert rois == sorted(rois)
    assert all(row["fixtures"] >= 2 for row in body["table"])
    assert body["groups_shown"] < body["groups_total"]


@pytest.mark.parametrize("key", [d.key for d in agg.DIMENSIONS])
def test_explore_every_dimension(client, key):
    body = strict_json(client.get("/api/explore", params={"group_by": key}))
    assert body["status"] == "ok"
    assert body["groups_total"] >= 1


def test_explore_filters(client, df):
    body = strict_json(
        client.get(
            "/api/explore",
            params={
                "date_from": "2025-03-01",
                "date_to": "2025-03-01",
                "market_type": ["ou", "ah"],
                "bookie": ["pinnacle"],
                "group_by": "selection",
            },
        )
    )
    matched = loader.matched(df)
    picked = matched[
        (matched["event_day"] == "2025-03-01")
        & matched["market_type"].astype("string").isin(["ou", "ah"])
        & (matched["bookie"].astype("string") == "pinnacle")
    ]
    assert body["view"]["turnover"] == pytest.approx(picked["turnover"].sum())
    assert {row["slice"] for row in body["table"]} == {"over", "under"}


def test_explore_stake_range_invalid(client):
    body = strict_json(
        client.get("/api/explore", params={"min_stake": 5, "max_stake": 2})
    )
    assert body == {
        "status": "stake_range_invalid",
        "message": "Maximum stake (2.00) is below the minimum (5.00) — no row can satisfy both.",
    }


def test_explore_empty(client):
    body = strict_json(
        client.get("/api/explore", params={"date_from": "2030-01-01"})
    )
    assert body == {"status": "empty", "message": "No rows match those filters."}


def test_explore_rejects_unknown_dimension(client):
    assert client.get("/api/explore", params={"group_by": "odds"}).status_code == 422


def test_explore_curves_only_for_eligible_groups(client, monkeypatch):
    # The synthetic frame is tiny; lower the bar so something qualifies.
    monkeypatch.setattr(agg, "SMALL_MULTIPLE_MIN_TURNOVER", 50.0)
    monkeypatch.setattr(agg, "SMALL_MULTIPLE_MIN_BETS", 1)
    body = strict_json(client.get("/api/explore", params={"group_by": "bookie"}))
    assert body["eligible"] == ["pinnacle", "betfair"]
    assert set(body["curves"]) == set(body["eligible"])
    months = [p["month"] for p in body["curves"]["pinnacle"]]
    assert months == sorted(months)
    last = body["curves"]["pinnacle"][-1]
    assert last["cum_roi_pct"] == pytest.approx(
        100 * last["cum_pl"] / last["cum_turnover"]
    )


def test_explore_without_eligible_groups(client):
    body = strict_json(client.get("/api/explore"))
    assert body["eligible"] == []
    assert body["curves"] == {}


# --------------------------------------------------------------------------
# Upload
# --------------------------------------------------------------------------


def post_csv(client, path: Path, **form):
    with path.open("rb") as fh:
        return client.post(
            "/api/upload", files={"file": (path.name, fh, "text/csv")}, data=form
        )


def test_upload_describes_the_file(client, modern_csv: Path):
    body = strict_json(post_csv(client, modern_csv))
    frame = loader.load_file(modern_csv)
    typical = round(loader.typical_stake(frame), 2)

    assert body["file"] == {
        "name": modern_csv.name,
        "currency_in_file": "EUR",
        "typical_stake": typical,
        "unit_used": typical,
        "fx": None,
    }
    assert body["checks"]["ok"] is True
    assert body["currency"]["currency"] == "EUR"
    assert body["units"]["currency"] == "units"
    assert [d["key"] for d in body["units"]["explore_options"]["dimensions"]] == [d.key for d in agg.DIMENSIONS]


def test_dimensions_carry_their_help_text(client, modern_csv: Path):
    body = strict_json(post_csv(client, modern_csv))
    help_text = {
        d["key"]: d["help"] for d in body["units"]["explore_options"]["dimensions"]
    }
    assert "one bookie" in help_text["position_size"]
    assert help_text["market_type"] is None


def test_explore_upload_in_currency_keeps_unit_position_sizes(client, modern_csv: Path):
    def buckets(**form):
        with modern_csv.open("rb") as fh:
            body = strict_json(
                client.post(
                    "/api/explore/upload",
                    files={"file": (modern_csv.name, fh, "text/csv")},
                    data=form,
                    params={"group_by": "position_size"},
                )
            )
        return body["currency"], sorted(r["slice"] for r in body["table"])

    units_label, in_units = buckets(unit="10")
    eur_label, in_eur = buckets(unit="10", in_units="false")
    assert (units_label, eur_label) == ("units", "EUR")
    assert in_units == in_eur


def test_upload_with_a_chosen_unit(client, modern_csv: Path):
    assert strict_json(post_csv(client, modern_csv, unit=10))["file"]["unit_used"] == 10


def test_upload_rejects_a_non_positive_unit(client, modern_csv: Path):
    assert post_csv(client, modern_csv, unit=0).status_code == 422


def test_upload_missing_required_column_is_a_clear_400(client, export_without):
    response = post_csv(client, export_without("Customer P/L"))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("partial.csv: missing required column(s) ['Customer P/L']")
    assert "Got:" in detail


def test_upload_full_export_misses_nothing(client, modern_csv: Path):
    body = strict_json(post_csv(client, modern_csv))
    assert body["missing_columns"] == []
    assert [d["key"] for d in body["units"]["explore_options"]["dimensions"]] == [d.key for d in agg.DIMENSIONS]


def test_upload_without_grouping_columns_hides_those_dimensions(
    client, export_without
):
    body = strict_json(post_csv(client, export_without("Bookie", "Country")))
    assert body["missing_columns"] == ["Country", "Bookie"]
    keys = [d["key"] for d in body["units"]["explore_options"]["dimensions"]]
    assert "bookie" not in keys and "country" not in keys
    assert "competition" in keys
    assert [d["key"] for d in body["currency"]["explore_options"]["dimensions"]] == keys


def test_upload_without_nr_of_bets_reports_bets_as_unknown(client, export_without):
    path = export_without("Nr of Bets")
    body = strict_json(post_csv(client, path))
    assert "n_bets_bucket" not in [d["key"] for d in body["units"]["explore_options"]["dimensions"]]
    explored = strict_json(explore_csv(client, path))
    assert explored["view"]["bets"] is None
    for row in explored["table"]:
        assert row["bets"] is None and row["bets_per_fixture"] is None
        assert row["fixtures"] >= 1


def test_upload_with_only_the_required_columns(client, export_without):
    optional = [h for h in RAW_HEADER if h not in UPLOAD_REQUIRED_HEADERS]
    path = export_without(*optional)
    body = strict_json(post_csv(client, path))
    assert sorted(body["missing_columns"]) == sorted(optional)
    assert [d["key"] for d in body["units"]["explore_options"]["dimensions"]] == [
        "position_size", "year", "month", "weekday"
    ]
    group_by = {"group_by": "year"}
    assert strict_json(explore_csv(client, path, **group_by))["view"]["fixtures"] == 3
    assert body["checks"]["ok"]
    skipped = [c["name"] for c in body["checks"]["checks"] if c["detail"].startswith("skipped:")]
    assert set(skipped) == {
        "roi_consistent", "turnover_within_stake", "market_types_known"
    }


def test_upload_garbage_is_a_400_not_a_500(client, tmp_path: Path):
    junk = tmp_path / "junk.csv"
    junk.write_bytes(b"\x00\x01\x02 not a csv at all")
    response = post_csv(client, junk)
    assert response.status_code == 400


def test_upload_never_writes_to_disk(client, modern_csv: Path, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    assert strict_json(post_csv(client, modern_csv))
    assert set(tmp_path.iterdir()) == before


def test_upload_with_no_matched_rows(client, tmp_path: Path):
    """An export where nothing matched: no typical stake, unit defaults to 1."""
    from conftest import RAW_HEADER, RAW_ROWS

    rows = [list(r) for r in RAW_ROWS]
    for r in rows:
        r[12] = 0.0  # Customer turnover
        r[13] = 0.0
        r[14] = 0.0
        r[15] = None
    path = tmp_path / "unmatched.csv"
    pd.DataFrame(rows, columns=RAW_HEADER).to_csv(path, index=False)
    body = strict_json(post_csv(client, path))
    assert body["file"]["typical_stake"] is None
    assert body["file"]["unit_used"] == 1.0
    assert body["units"]["explore_options"] is None
    assert body["currency"]["explore_options"] is None


# --------------------------------------------------------------------------
# Explore an uploaded file
# --------------------------------------------------------------------------


def explore_csv(client, path: Path, unit: float | None = None, **params):
    form = {} if unit is None else {"unit": str(unit)}
    with path.open("rb") as fh:
        return client.post(
            "/api/explore/upload",
            files={"file": (path.name, fh, "text/csv")},
            data=form,
            params=params,
        )


def test_explore_upload_covers_only_the_file(client, modern_csv: Path):
    body = strict_json(explore_csv(client, modern_csv, group_by="bookie"))
    matched = loader.matched(loader.load_file(modern_csv))
    assert body["status"] == "ok"
    assert body["view"]["turnover"] == pytest.approx(matched["turnover"].sum())
    assert {r["slice"] for r in body["table"]} == set(
        matched["bookie"].astype(str)
    )
    assert body["curve_bucket"] == "day"
    assert body["view"]["fixtures"] == matched["fixture_id"].nunique()


def test_explore_upload_running_pl_follows_the_filters(client, modern_csv: Path):
    everything = strict_json(explore_csv(client, modern_csv))["cumulative"]
    ou_only = strict_json(explore_csv(client, modern_csv, market_type=["ou"]))
    matched = loader.matched(loader.load_file(modern_csv))
    ou = matched[matched["market_type"] == "ou"]
    assert everything["bucket"] == "day"
    points = ou_only["cumulative"]["points"]
    assert points[-1]["cumulative_pl"] == pytest.approx(ou["pl"].sum())
    assert points != everything["points"]


def test_explore_history_curves_stay_monthly(client):
    body = strict_json(client.get("/api/explore"))
    assert body["curve_bucket"] == "month"
    # The history's running P/L is on the Overview tab, not repeated here.
    assert body["cumulative"] is None


def test_explore_upload_in_units(client, modern_csv: Path):
    raw = strict_json(explore_csv(client, modern_csv))
    units = strict_json(explore_csv(client, modern_csv, unit=2.0))
    assert units["currency"] == "units"
    assert units["view"]["turnover"] == pytest.approx(raw["view"]["turnover"] / 2)
    assert units["view"]["roi_pct"] == pytest.approx(raw["view"]["roi_pct"])


def test_explore_upload_filters_like_the_history(client, modern_csv: Path):
    body = strict_json(
        explore_csv(client, modern_csv, market_type=["ou"], group_by="bookie")
    )
    matched = loader.matched(loader.load_file(modern_csv))
    ou = matched[matched["market_type"] == "ou"]
    assert body["view"]["turnover"] == pytest.approx(ou["turnover"].sum())


def test_explore_upload_without_a_column(client, export_without):
    path = export_without("Bookie", "Stake", "Nr of Bets")
    by_bookie = strict_json(explore_csv(client, path, group_by="bookie"))
    assert by_bookie["status"] == "empty"
    # Filters on absent columns are ignored rather than emptying the view.
    body = strict_json(
        explore_csv(client, path, bookie=["pinnacle"], min_stake=10, max_stake=20)
    )
    assert body["status"] == "ok"
    assert body["view"]["bets"] is None


def test_upload_carries_explore_options_for_the_file(client, export_without):
    body = strict_json(post_csv(client, export_without("Bookie", "Stake")))
    options = body["units"]["explore_options"]
    assert options["currency"] == "units"
    assert options["stake_ceiling"] is None
    assert options["bookies"] == []
    assert "bookie" not in [d["key"] for d in options["dimensions"]]
    assert options["compare"]["min_bets"] is None
    assert options["compare"]["min_fixtures"] == agg.UPLOAD_CURVE_MIN_FIXTURES
    assert body["currency"]["explore_options"]["currency"] == "EUR"


def test_explore_upload_rejects_a_broken_file(client, export_without):
    assert explore_csv(client, export_without("Event")).status_code == 400


# --------------------------------------------------------------------------
# Currency conversion. The rate service is stubbed: no test touches the network.
# --------------------------------------------------------------------------


@pytest.fixture
def sek_rate(monkeypatch):
    rate = fx.Rate("EUR", "SEK", 11.0, "2026-09-25")
    calls: list[tuple[str, str]] = []

    def fake(base, target):
        calls.append((base, target))
        return rate

    monkeypatch.setattr(fx, "latest", fake)
    return calls


def test_upload_converts_the_currency_view(client, modern_csv: Path, sek_rate):
    eur = strict_json(post_csv(client, modern_csv))
    sek = strict_json(post_csv(client, modern_csv, currency="SEK"))
    assert sek_rate == [("EUR", "SEK")]
    assert sek["currency"]["currency"] == "SEK"
    assert sek["currency"]["explore_options"]["currency"] == "SEK"
    assert sek["file"]["fx"] == {
        "base": "EUR", "target": "SEK", "rate": 11.0, "date": "2026-09-25"
    }
    # The unit follows the currency: the typical stake is now in SEK.
    assert sek["file"]["typical_stake"] == pytest.approx(
        11.0 * eur["file"]["typical_stake"], abs=0.01
    )


def test_a_unit_keeps_its_worth_in_another_currency(client, modern_csv, sek_rate):
    """1 unit = 10 EUR, shown in SEK, is 1 unit = 110 SEK — not 10 SEK."""
    sek = strict_json(
        post_csv(client, modern_csv, unit=10, unit_currency="EUR", currency="SEK")
    )
    assert sek["file"]["unit_used"] == 110


def test_a_unit_without_its_currency_is_in_the_shown_one(client, modern_csv, sek_rate):
    body = strict_json(post_csv(client, modern_csv, unit=100, currency="SEK"))
    assert body["file"]["unit_used"] == 100


def test_upload_in_its_own_currency_fetches_no_rate(client, modern_csv, sek_rate):
    body = strict_json(post_csv(client, modern_csv, currency="EUR"))
    assert sek_rate == []
    assert body["file"]["fx"] is None


def test_upload_rejects_an_unsupported_currency(client, modern_csv: Path):
    assert post_csv(client, modern_csv, currency="GBP").status_code == 422


def test_rate_unavailable_is_a_clear_503(client, modern_csv: Path, monkeypatch):
    def down(base, target):
        raise fx.FxUnavailableError("Could not fetch today's EUR/SEK exchange rate.")

    monkeypatch.setattr(fx, "latest", down)
    response = post_csv(client, modern_csv, currency="SEK")
    assert response.status_code == 503
    assert "exchange rate" in response.json()["detail"]


def test_explore_upload_converts_too(client, modern_csv: Path, sek_rate):
    eur = strict_json(explore_csv(client, modern_csv))
    with modern_csv.open("rb") as fh:
        sek = strict_json(
            client.post(
                "/api/explore/upload",
                files={"file": (modern_csv.name, fh, "text/csv")},
                data={"currency": "SEK"},
            )
        )
    assert sek["currency"] == "SEK"
    assert sek["view"]["turnover"] == pytest.approx(11.0 * eur["view"]["turnover"])
    assert sek["view"]["roi_pct"] == pytest.approx(eur["view"]["roi_pct"])


def test_explore_upload_units_are_in_the_shown_currency(client, modern_csv, sek_rate):
    eur = strict_json(explore_csv(client, modern_csv))
    with modern_csv.open("rb") as fh:
        units = strict_json(
            client.post(
                "/api/explore/upload",
                files={"file": (modern_csv.name, fh, "text/csv")},
                data={"currency": "SEK", "unit": "110"},
            )
        )
    assert units["currency"] == "units"
    assert units["view"]["turnover"] == pytest.approx(eur["view"]["turnover"] / 10)
