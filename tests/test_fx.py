"""api/fx.py, with the network replaced: the rate service is never called."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from api import fx


@pytest.fixture(autouse=True)
def empty_cache():
    fx._cache.clear()
    yield
    fx._cache.clear()


def _serve(monkeypatch, payload: dict) -> list[str]:
    urls: list[str] = []

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        assert request.get_header("User-agent") == fx.USER_AGENT
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(fx.urllib.request, "urlopen", fake_urlopen)
    return urls


def test_latest_reads_the_ecb_rate(monkeypatch):
    urls = _serve(monkeypatch, {"date": "2026-09-25", "rates": {"SEK": 11.29}})
    rate = fx.latest("EUR", "SEK")
    assert rate == fx.Rate("EUR", "SEK", 11.29, "2026-09-25")
    assert urls == ["https://api.frankfurter.dev/v1/latest?base=EUR&symbols=SEK"]


def test_latest_is_cached(monkeypatch):
    urls = _serve(monkeypatch, {"date": "2026-09-25", "rates": {"USD": 1.14}})
    fx.latest("EUR", "USD")
    fx.latest("EUR", "USD")
    assert len(urls) == 1


def test_unreachable_service_raises_a_readable_error(monkeypatch):
    def down(request, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(fx.urllib.request, "urlopen", down)
    with pytest.raises(fx.FxUnavailableError, match="EUR/SEK exchange rate"):
        fx.latest("EUR", "SEK")


def test_malformed_answer_raises_too(monkeypatch):
    _serve(monkeypatch, {"date": "2026-09-25", "rates": {}})
    with pytest.raises(fx.FxUnavailableError):
        fx.latest("EUR", "SEK")
