"""Today's exchange rate, for showing an uploaded file in another currency.

Sportmarket Pro exports are in EUR. A viewer who thinks in SEK or USD can see
the same file converted at the European Central Bank's latest reference rate,
fetched from Frankfurter (https://frankfurter.dev), a free service that
republishes the ECB rates. One rate for the whole file, not one per match day:
"126 EUR is about 1,420 SEK today" is the figure a person can check.

Only the two currency codes are sent; nothing from the file leaves the server.
The ECB publishes once per working day, so a rate is kept for an hour rather
than fetched on every request. When the service cannot be reached, the caller
says so instead of showing unconverted amounts under a converted label.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

URL = "https://api.frankfurter.dev/v1/latest?base={base}&symbols={target}"
TIMEOUT_SECONDS = 5
#: The service sits behind Cloudflare, which answers Python's default
#: "Python-urllib" user agent with 403. Name the app instead.
USER_AGENT = "sportmarket-analysis (+https://sportbetting-analysis-tool.vercel.app)"
CACHE_SECONDS = 60 * 60


class FxUnavailableError(RuntimeError):
    """Raised when no rate can be had. The message is fit to show a person."""


@dataclass(frozen=True)
class Rate:
    """``1 base = rate target``, as published by the ECB on ``date``."""

    base: str
    target: str
    rate: float
    date: str


_cache: dict[tuple[str, str], tuple[float, Rate]] = {}


def _fetch(base: str, target: str) -> Rate:
    request = urllib.request.Request(
        URL.format(base=base, target=target), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.load(response)
        return Rate(base, target, float(body["rates"][target]), str(body["date"]))
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        raise FxUnavailableError(
            f"Could not fetch today's {base}/{target} exchange rate. "
            "Try again in a moment, or show the amounts in "
            f"{base}."
        ) from exc


def latest(base: str, target: str) -> Rate:
    """Today's rate from ``base`` to ``target``.

    Raises :class:`FxUnavailableError` when it cannot be fetched.
    """
    now = time.monotonic()
    cached = _cache.get((base, target))
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    rate = _fetch(base, target)
    _cache[(base, target)] = (now, rate)
    return rate
