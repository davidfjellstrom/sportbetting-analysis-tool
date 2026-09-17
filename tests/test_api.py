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
from api.history import History, get_history
from api.index import app


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
    assert body["compare"] == {"min_turnover": 350.0, "min_bets": 2000, "max_series": 8}


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


def test_upload_returns_both_views(client, modern_csv: Path):
    body = strict_json(post_csv(client, modern_csv))
    frame = loader.load_file(modern_csv)
    matched = loader.matched(frame)
    typical = round(loader.typical_stake(frame), 2)

    assert body["file"] == {
        "name": modern_csv.name,
        "currency_in_file": "EUR",
        "typical_stake": typical,
        "unit_used": typical,
    }
    assert body["checks"]["ok"] is True
    assert body["report"]["n_rows"] == len(frame)
    assert body["report"]["n_unmatched_rows"] == 1

    assert body["currency"]["currency"] == "EUR"
    assert body["currency"]["matched"]["turnover"] == pytest.approx(
        matched["turnover"].sum()
    )
    assert body["units"]["currency"] == "units"
    assert body["units"]["matched"]["turnover"] == pytest.approx(
        matched["turnover"].sum() / typical
    )
    assert body["units"]["matched"]["bets"] == body["currency"]["matched"]["bets"]

    assert body["units"]["cumulative"]["bucket"] == "day"
    assert set(body["units"]["breakdown"]) == {d.key for d in agg.DIMENSIONS}
    for rows in body["units"]["breakdown"].values():
        turnovers = [r["turnover"] for r in rows]
        assert turnovers == sorted(turnovers, reverse=True)


def test_upload_stake_buckets_differ_between_views(client, modern_csv: Path):
    """Stake buckets are cut on the stake column, so the two views disagree."""
    body = strict_json(post_csv(client, modern_csv))
    in_currency = {r["slice"] for r in body["currency"]["breakdown"]["stake_bucket"]}
    in_units = {r["slice"] for r in body["units"]["breakdown"]["stake_bucket"]}
    assert in_currency == {"10+"}
    assert in_units != in_currency


def test_upload_with_a_chosen_unit(client, modern_csv: Path):
    body = strict_json(post_csv(client, modern_csv, unit=10))
    frame = loader.matched(loader.load_file(modern_csv))
    assert body["file"]["unit_used"] == 10
    assert body["units"]["matched"]["pl"] == pytest.approx(frame["pl"].sum() / 10)


def test_upload_rejects_a_non_positive_unit(client, modern_csv: Path):
    assert post_csv(client, modern_csv, unit=0).status_code == 422


def test_upload_missing_column_is_a_clear_400(client, tmp_path: Path):
    broken = tmp_path / "broken.csv"
    original = pd.DataFrame(
        {
            "Event": ["A v B"],
            "Market": ["Football"],
            "Market Type": ["ou"],
            "Selection": ["over"],
            "Country": ["Spain"],
            "Event Type": ["normal"],
            "Competition": ["La Liga"],
            "Bookie": ["pinnacle"],
            "Event Day": ["2025-03-01"],
            "Nr of Bets": [1],
            "Customer turnover": [10.0],
            "Customer P/L": [-10.0],
            "ROI": [-1.0],
        }
    )
    original.to_csv(broken, index=False)  # no "Stake" column
    response = post_csv(client, broken)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("broken.csv: missing required column(s) ['stake']")
    assert "Got:" in detail


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
    assert body["units"]["matched"]["turnover"] == 0
    assert body["units"]["cumulative"]["points"] == []
    assert body["report"]["n_unmatched_rows"] == len(rows)
