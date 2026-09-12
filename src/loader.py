"""Loading and normalisation of Sportmarket Pro exports.

This module owns everything between "CSV on disk" and "a tidy DataFrame".
It deliberately computes nothing: no implied odds, no features, no statistics.
Those live in ``odds.py``, ``features.py`` and ``stats.py``.

Two schema facts drive most of the code here (CLAUDE.md -> Critical facts):

* A row is an aggregate of ``n_bets`` individual bets, not a single bet.
* ``stake`` is the intended stake; ``turnover`` is what actually matched.
  Rows with ``turnover == 0`` are unmatched and belong in no performance
  calculation. Use :func:`matched` to drop them, explicitly, once.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"

#: Source header -> internal snake_case name.
COLUMN_MAP: dict[str, str] = {
    "Event": "event",
    "Market": "market",
    "Market Type": "market_type",
    "Selection": "selection",
    "Country": "country",
    "Competition": "competition",
    "Event Type": "event_type",
    "Bookie": "bookie",
    "Event Day": "event_day",
    "Nr of Bets": "n_bets",
    "Stake": "stake",
    "Customer turnover": "turnover",
    "Customer price adjusted turnover": "price_adjusted_turnover",
    "Customer currency": "currency",
    "Customer P/L": "pl",
    "ROI": "roi",
}

#: Columns every export must carry.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "event",
    "market",
    "market_type",
    "selection",
    "country",
    "competition",
    "event_type",
    "bookie",
    "event_day",
    "n_bets",
    "stake",
    "turnover",
    "pl",
    "roi",
)

#: Not required, but kept when present. ``price_adjusted_turnover`` is
#: populated from 2025 onwards only; ``currency`` exists so ``checks.py`` can
#: prove every amount is in one currency instead of assuming it.
OPTIONAL_COLUMNS: tuple[str, ...] = ("price_adjusted_turnover", "currency")

NUMERIC_COLUMNS: tuple[str, ...] = (
    "n_bets",
    "stake",
    "turnover",
    "price_adjusted_turnover",
    "pl",
    "roi",
)

CATEGORICAL_COLUMNS: tuple[str, ...] = (
    "currency",
    "market_type",
    "selection",
    "country",
    "competition",
    "event_type",
    "bookie",
)

#: The clustering unit for every standard error in this repo (CLAUDE.md rule 1).
FIXTURE_KEY: tuple[str, ...] = ("event", "event_day")

#: Grouping key for the both-sides-of-one-market check (features.py).
POSITION_KEY: tuple[str, ...] = ("event", "event_day", "market", "market_type")

#: Market types treated as novelty markets; negative in both periods.
NOVELTY_MARKET_TYPES: frozenset[str] = frozenset({"cs", "score", "custom"})


class SchemaError(ValueError):
    """Raised when an export does not look like a Sportmarket Pro CSV."""


@dataclass(frozen=True)
class LoadReport:
    """What a load actually produced. Print this; do not trust silence."""

    files: tuple[str, ...]
    n_rows: int
    n_bets: int
    n_fixtures: int
    n_unmatched_rows: int
    turnover: float
    date_min: pd.Timestamp | None
    date_max: pd.Timestamp | None
    has_price_adjusted_turnover: bool
    price_adjusted_coverage: float

    def __str__(self) -> str:  # pragma: no cover - presentation only
        span = (
            f"{self.date_min:%Y-%m-%d} .. {self.date_max:%Y-%m-%d}"
            if self.date_min is not None
            else "empty"
        )
        return (
            f"{len(self.files)} file(s), {self.n_rows:,} rows "
            f"({self.n_bets:,} bets, {self.n_fixtures:,} fixtures), {span}\n"
            f"  turnover {self.turnover:,.0f} | unmatched rows "
            f"{self.n_unmatched_rows:,} ({self.unmatched_row_share:.1%})\n"
            f"  price-adjusted turnover on {self.price_adjusted_coverage:.1%} of rows"
        )

    @property
    def unmatched_row_share(self) -> float:
        return self.n_unmatched_rows / self.n_rows if self.n_rows else 0.0


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename source headers to snake_case, tolerating whitespace and case."""
    lookup = {k.strip().casefold(): v for k, v in COLUMN_MAP.items()}
    renamed = {}
    for col in df.columns:
        key = str(col).strip().casefold()
        renamed[col] = lookup.get(key, str(col).strip().casefold().replace(" ", "_"))
    return df.rename(columns=renamed)


def _check_schema(df: pd.DataFrame, source: str) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(
            f"{source}: missing required column(s) {missing}. "
            f"Got: {sorted(df.columns)}"
        )


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["event_day"] = pd.to_datetime(df["event_day"], errors="coerce", format="mixed")

    for col in ("event", "market"):
        df[col] = df[col].astype("string").str.strip()
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            df[col] = (
                df[col].astype("string").str.strip().str.lower().astype("category")
            )

    return df


def add_fixture_id(df: pd.DataFrame) -> pd.DataFrame:
    """Attach ``fixture_id``, the ``event + event_day`` clustering unit.

    Every clustered bootstrap, every out-of-sample split and every "how many
    fixtures back this slice?" threshold resamples on this column, never on
    rows. It is added here so no downstream module has to reinvent the key.
    """
    df = df.copy()
    df["fixture_id"] = (
        df["event"].astype("string").fillna("?")
        + " @ "
        + df["event_day"].dt.strftime("%Y-%m-%d").fillna("?")
    )
    return df


def _build(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    """Normalise one export, whatever it was read from. Drops nothing."""
    df = normalise_columns(raw)
    _check_schema(df, source)
    df = _coerce_types(df)
    df = add_fixture_id(df)
    df["source_file"] = source
    keep = [
        c
        for c in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS, "fixture_id", "source_file")
        if c in df.columns
    ]
    return df[keep]


def load_file(path: str | Path) -> pd.DataFrame:
    """Read one yearly export. Normalises names and types; drops nothing."""
    path = Path(path)
    return _build(pd.read_csv(path), path.name)


def load_upload(buffer, name: str) -> pd.DataFrame:
    """Read an export from an open buffer — a Streamlit upload, say.

    Same pipeline as :func:`load_file`; the filename is passed separately
    because a buffer has no path to take it from, and ``source_file`` is what
    tells a merged frame which rows arrived this way.
    """
    return _build(pd.read_csv(buffer), name)


def load_raw(
    data_dir: str | Path = DEFAULT_RAW_DIR,
    pattern: str = "*.csv",
) -> pd.DataFrame:
    """Read and concatenate every yearly export in ``data_dir``.

    Files without ``price_adjusted_turnover`` (pre-2025) get the column as NaN,
    which is the honest representation: the value is absent, not zero.
    """
    data_dir = Path(data_dir)
    paths = sorted(p for p in data_dir.glob(pattern) if p.is_file())
    if not paths:
        raise FileNotFoundError(
            f"No files matching {pattern!r} in {data_dir}. "
            "The exports are gitignored on purpose; copy them in by hand."
        )

    frames = [load_file(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    if "price_adjusted_turnover" not in df.columns:
        df["price_adjusted_turnover"] = pd.NA
    return df.sort_values(["event_day", "event"], kind="stable").reset_index(drop=True)


def matched(df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose stake actually matched. Excludes ``turnover == 0``.

    Overall fill rate is roughly 88%; the unmatched rows are attempted bets
    with no exposure and must not enter any performance calculation.
    """
    return df.loc[df["turnover"] > 0].copy()


def unmatched(df: pd.DataFrame) -> pd.DataFrame:
    """The complement of :func:`matched` — worth studying separately."""
    return df.loc[df["turnover"].fillna(0) <= 0].copy()


def fill_rate(df: pd.DataFrame) -> float:
    """Turnover-weighted fill rate: matched turnover / intended stake."""
    stake = float(df["stake"].sum())
    return float(df["turnover"].sum()) / stake if stake else float("nan")


def period(df: pd.DataFrame, start: str | None = None, end: str | None = None):
    """Inclusive date slice on ``event_day``, for build/test window splits."""
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df["event_day"] >= pd.Timestamp(start)
    if end is not None:
        mask &= df["event_day"] <= pd.Timestamp(end)
    return df.loc[mask].copy()


def describe(df: pd.DataFrame, files: tuple[str, ...] = ()) -> LoadReport:
    """Summarise a loaded frame. Cheap sanity check after every load."""
    if not files and "source_file" in df.columns:
        files = tuple(sorted(df["source_file"].dropna().unique().tolist()))
    pat_coverage = 0.0
    if "price_adjusted_turnover" in df.columns and len(df):
        pat_coverage = float(df["price_adjusted_turnover"].notna().mean())
    return LoadReport(
        files=files,
        n_rows=len(df),
        n_bets=int(df["n_bets"].fillna(0).sum()),
        n_fixtures=int(df["fixture_id"].nunique()) if "fixture_id" in df else 0,
        n_unmatched_rows=int((df["turnover"].fillna(0) <= 0).sum()),
        turnover=float(df["turnover"].fillna(0).sum()),
        date_min=df["event_day"].min() if len(df) else None,
        date_max=df["event_day"].max() if len(df) else None,
        has_price_adjusted_turnover="price_adjusted_turnover" in df.columns,
        price_adjusted_coverage=pat_coverage,
    )
