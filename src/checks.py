"""Data-integrity battery: what is actually true of the exports on disk.

This module exists because the facts in ``CLAUDE.md`` were once established by
hand, in a session that is now gone, and the repo had no way to prove any of
them again. A claim nobody can re-run is a claim that quietly rots. Everything
here was verified against the real exports before being written down, and is
phrased so a future export that breaks the assumption says so out loud.

**It reports; it does not repair.** Nothing in this module drops a row, fills a
gap or rounds a number. That is the same stance ``loader.py`` takes and for the
same reason: every silent repair converts an "I don't know" into a number, and
the error then becomes invisible forever. A failing check is information, not a
crash — call :meth:`CheckReport.raise_if_errors` when you want it to be fatal
(CI does), and otherwise print the report and decide.

Severity is about consequence, not tidiness:

``ERROR``
    The analysis would be wrong. Mixed currencies, ``roi`` that disagrees with
    ``pl / turnover``, matched turnover exceeding the stake that was offered.

``WARN``
    Worth a human's attention, does not invalidate anything on its own. An
    unrecognised market type, exact duplicate rows, unmatched rows that
    nevertheless carry a result.

``INFO``
    Never fails. Coverage figures that belong next to the checks so a drifting
    dataset is visible at a glance rather than after someone goes looking.

Usage::

    df = loader.load_raw()
    report = checks.run_checks(df)
    print(report)
    report.raise_if_errors()   # in CI, or before publishing a result
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

#: Every market type observed in the exports so far. Core and novelty types
#: are named in CLAUDE.md; the rest are a rare long tail. An unseen type is a
#: WARN, not an ERROR — new bet types appear over time and that is normal. It
#: should still be noticed.
KNOWN_MARKET_TYPES: frozenset[str] = frozenset(
    {
        # core
        "ah", "ahou", "ou", "1x2", "taou",
        # novelty (negative in both periods)
        "cs", "score", "custom",
        # long tail
        "aou", "eh", "extot", "gr", "ml", "moscore", "other", "props",
        "qualify", "swm", "win", "wm", "wtn",
    }
)

#: ``roi`` is stored to full float precision in the export; the largest
#: disagreement with ``pl / turnover`` observed anywhere is 1.4e-14. The
#: tolerance is loose enough to survive a future export that rounds, tight
#: enough that a genuinely inconsistent row cannot hide behind it.
ROI_TOLERANCE: float = 1e-4

#: ``price_adjusted_turnover = turnover * min(1, odds - 1)`` bounds the ratio
#: at 1. The observed maximum is 1.0227 (see the 2.023 figure in CLAUDE.md),
#: so anything past 1.05 means the derivation itself no longer holds.
MAX_PAT_RATIO: float = 1.05

#: Fixtures outside this window mean a corrupt date, not a real match.
PLAUSIBLE_DATE_RANGE: tuple[str, str] = ("2022-01-01", "2030-01-01")


class Severity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class IntegrityError(ValueError):
    """Raised by :meth:`CheckReport.raise_if_errors` when an ERROR check fails."""


@dataclass(frozen=True)
class Check:
    """One verified claim about the data, and whether it still holds."""

    name: str
    passed: bool
    severity: Severity
    detail: str

    def __str__(self) -> str:  # pragma: no cover - presentation only
        mark = (
            "  "
            if self.severity is Severity.INFO
            else ("ok" if self.passed else "!!")
        )
        return f"  [{mark}] {self.severity.value:<5} {self.name}: {self.detail}"


@dataclass(frozen=True)
class CheckReport:
    """The outcome of a full run. Print it; do not trust silence."""

    checks: tuple[Check, ...]

    @property
    def failed(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if not c.passed)

    @property
    def errors(self) -> tuple[Check, ...]:
        return tuple(c for c in self.failed if c.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Check, ...]:
        return tuple(c for c in self.failed if c.severity is Severity.WARN)

    @property
    def ok(self) -> bool:
        """True when nothing that would invalidate the analysis failed."""
        return not self.errors

    def raise_if_errors(self) -> None:
        """Turn ERROR failures into an exception. WARNs never raise."""
        if self.errors:
            joined = "\n".join(f"  - {c.name}: {c.detail}" for c in self.errors)
            raise IntegrityError(
                f"{len(self.errors)} integrity check(s) failed:\n{joined}"
            )

    def __str__(self) -> str:  # pragma: no cover - presentation only
        head = (
            f"{len(self.checks)} checks: {len(self.errors)} error(s), "
            f"{len(self.warnings)} warning(s)"
        )
        return "\n".join([head, *(str(c) for c in self.checks)])


# --------------------------------------------------------------------------
# Individual checks. Each takes the loaded frame and returns one Check, so a
# caller can run just the one they care about and tests can target them.
# --------------------------------------------------------------------------


def check_single_currency(df: pd.DataFrame) -> Check:
    """Every amount must be in one currency, or sums are meaningless.

    All five exports are EUR. The loader keeps the column purely so this can be
    proved rather than assumed: a single non-EUR row would otherwise be added
    to the totals with no complaint.
    """
    if "currency" not in df.columns:
        return Check(
            "single_currency", True, Severity.INFO, "no currency column in export"
        )
    seen = sorted(str(v) for v in df["currency"].dropna().unique())
    return Check(
        "single_currency",
        len(seen) <= 1,
        Severity.ERROR,
        f"currencies present: {seen or ['none']}",
    )


def check_roi_consistent(df: pd.DataFrame) -> Check:
    """``roi`` must equal ``pl / turnover`` on every matched row.

    If it does not, one of the two is measuring something else and every yield
    in the repo is built on the wrong one.
    """
    m = df.loc[df["turnover"] > 0]
    if m.empty:
        return Check("roi_consistent", True, Severity.ERROR, "no matched rows")
    diff = (m["pl"] / m["turnover"] - m["roi"]).abs()
    bad = int((diff > ROI_TOLERANCE).sum())
    return Check(
        "roi_consistent",
        bad == 0,
        Severity.ERROR,
        f"max deviation {diff.max():.2e} over {len(m):,} matched rows"
        + (f", {bad:,} beyond tolerance" if bad else ""),
    )


def check_turnover_within_stake(df: pd.DataFrame) -> Check:
    """Matched turnover can never exceed the stake that was offered."""
    bad = int((df["turnover"] > df["stake"] + 1e-9).sum())
    return Check(
        "turnover_within_stake",
        bad == 0,
        Severity.ERROR,
        f"{bad:,} row(s) with turnover > stake",
    )


def check_amounts_non_negative(df: pd.DataFrame) -> Check:
    """Stake, turnover and bet counts are non-negative; ``pl`` of course is not."""
    cols = [c for c in ("stake", "turnover", "n_bets") if c in df.columns]
    bad = int((df[cols] < 0).any(axis=1).sum())
    n_bets_bad = int((df["n_bets"] < 1).sum()) if "n_bets" in df.columns else 0
    return Check(
        "amounts_non_negative",
        bad == 0 and n_bets_bad == 0,
        Severity.ERROR,
        f"{bad:,} row(s) negative, {n_bets_bad:,} row(s) with n_bets < 1",
    )


def check_pat_within_turnover(df: pd.DataFrame) -> Check:
    """``price_adjusted_turnover / turnover`` must respect the derivation.

    The ratio is bounded at 1 by ``min(1, odds - 1)``; the observed ceiling is
    1.0227. A ratio past :data:`MAX_PAT_RATIO` means the formula in
    ``odds.py`` no longer describes this export, and every derived odds is
    suspect.
    """
    if "price_adjusted_turnover" not in df.columns:
        return Check("pat_within_turnover", True, Severity.INFO, "column absent")
    m = df.loc[(df["turnover"] > 0) & df["price_adjusted_turnover"].notna()]
    if m.empty:
        return Check(
            "pat_within_turnover", True, Severity.INFO, "no populated rows"
        )
    ratio = m["price_adjusted_turnover"] / m["turnover"]
    bad = int(((ratio > MAX_PAT_RATIO) | (ratio < 0)).sum())
    return Check(
        "pat_within_turnover",
        bad == 0,
        Severity.ERROR,
        f"max ratio {ratio.max():.4f} (implied odds {1 + ratio.max():.4f})"
        + (f", {bad:,} out of bounds" if bad else ""),
    )


def check_event_day_parsed(df: pd.DataFrame) -> Check:
    """Every row needs a date, because the clustering unit is built from it.

    A NaT date collapses into the ``?`` fixture bucket, silently gluing
    unrelated bets into one cluster and corrupting every interval downstream.
    """
    bad = int(df["event_day"].isna().sum())
    return Check(
        "event_day_parsed",
        bad == 0,
        Severity.ERROR,
        f"{bad:,} row(s) with an unparseable Event Day",
    )


def check_dates_plausible(df: pd.DataFrame) -> Check:
    """Fixture dates fall inside a sane window."""
    lo, hi = (pd.Timestamp(x) for x in PLAUSIBLE_DATE_RANGE)
    day = df["event_day"]
    bad = int(((day < lo) | (day > hi)).sum())
    span = (
        f"{day.min():%Y-%m-%d} .. {day.max():%Y-%m-%d}"
        if day.notna().any()
        else "empty"
    )
    return Check(
        "dates_plausible",
        bad == 0,
        Severity.WARN,
        f"span {span}" + (f", {bad:,} outside {PLAUSIBLE_DATE_RANGE}" if bad else ""),
    )


def check_no_duplicate_rows(df: pd.DataFrame) -> Check:
    """Exact duplicates would double-count turnover and P/L.

    ``source_file`` is excluded from the comparison so the same row appearing
    in two yearly exports is caught rather than excused.
    """
    cols = [c for c in df.columns if c != "source_file"]
    bad = int(df.duplicated(subset=cols).sum())
    return Check(
        "no_duplicate_rows",
        bad == 0,
        Severity.WARN,
        f"{bad:,} exact duplicate row(s)",
    )


def check_market_types_known(df: pd.DataFrame) -> Check:
    """Flag market types never seen when the domain notes were written.

    Not an error: new bet types appear. But an unseen type is unclassified —
    nobody has decided whether it is a core market or a novelty one — and
    ``NOVELTY_MARKET_TYPES`` will silently treat it as core.
    """
    seen = {str(v) for v in df["market_type"].dropna().unique()}
    unknown = sorted(seen - KNOWN_MARKET_TYPES)
    return Check(
        "market_types_known",
        not unknown,
        Severity.WARN,
        f"{len(seen)} type(s) present"
        + (f"; unrecognised: {unknown}" if unknown else "; all recognised"),
    )


def check_unmatched_rows_carry_no_result(df: pd.DataFrame) -> Check:
    """A row with no matched stake should have no profit or loss.

    Rows that break this do occur in the exports. ``loader.matched`` drops
    them, so their P/L is excluded from every performance figure, and the
    headline P/L will then differ from the raw total by that amount. The
    discrepancy is deliberate, but it must stay visible.
    """
    odd = df.loc[(df["turnover"] <= 0) & (df["pl"] != 0)]
    excluded = float(odd["pl"].sum())
    return Check(
        "unmatched_rows_carry_no_result",
        odd.empty,
        Severity.WARN,
        f"{len(odd):,} unmatched row(s) carrying P/L, {excluded:+,.2f} excluded "
        "from every performance figure",
    )


def _info(df: pd.DataFrame) -> list[Check]:
    """Coverage figures. These never fail; they make drift visible."""
    out: list[Check] = []
    stake = float(df["stake"].sum())
    if stake:
        out.append(
            Check(
                "fill_rate",
                True,
                Severity.INFO,
                f"{float(df['turnover'].sum()) / stake:.1%} of stake matched; "
                f"{int((df['turnover'] <= 0).sum()):,} unmatched row(s)",
            )
        )
    if "selection" in df.columns:
        share = float(df["selection"].isna().mean())
        out.append(
            Check(
                "selection_coverage",
                True,
                Severity.INFO,
                f"{1 - share:.1%} of rows carry a side "
                "(absence is a category, never a filter)",
            )
        )
    if "price_adjusted_turnover" in df.columns:
        pat = df["price_adjusted_turnover"].notna()
        detail = f"{float(pat.mean()):.1%} of rows have the column"
        m = df.loc[pat & (df["turnover"] > 0)]
        if not m.empty:
            ratio = m["price_adjusted_turnover"] / m["turnover"]
            exact = float((ratio < 0.999).mean())
            detail += f"; {exact:.1%} of those give exact odds, rest censored"
        out.append(Check("odds_coverage", True, Severity.INFO, detail))
    return out


def run_checks(df: pd.DataFrame) -> CheckReport:
    """Run the whole battery over a loaded frame.

    Takes the output of :func:`loader.load_raw` — unmatched rows still
    present, since several checks are about exactly those rows.
    """
    checks = [
        check_single_currency(df),
        check_roi_consistent(df),
        check_turnover_within_stake(df),
        check_amounts_non_negative(df),
        check_pat_within_turnover(df),
        check_event_day_parsed(df),
        check_dates_plausible(df),
        check_no_duplicate_rows(df),
        check_market_types_known(df),
        check_unmatched_rows_carry_no_result(df),
        *_info(df),
    ]
    return CheckReport(tuple(checks))
