"""Estimation with fixture-clustered uncertainty.

    OWNER MODULE — see CLAUDE.md -> Division of labour.
    Scaffolding only: signatures and the rules they must enforce.

The rules are structural, not stylistic:

1. Cluster on ``fixture_id`` (``event + event_day``). Row-level standard errors
   badly understate uncertainty — several bets per match is the norm.
2. No point estimate without an interval. Nothing in this module may return a
   bare yield, ROI or edge; the return type should make that impossible.
3. Threshold on fixture count, not turnover.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Estimate:
    """A number that arrives with its uncertainty attached, or not at all.

    Suggested fields — settle them before writing the bootstrap:
    ``value``, ``ci_low``, ``ci_high``, ``level``, ``n_rows``, ``n_fixtures``,
    ``turnover``, ``adequate``.
    """


def yield_with_ci(df, level: float = 0.95, n_boot: int = 10_000) -> Estimate:
    """Turnover-weighted yield with a fixture-clustered bootstrap interval."""
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def clustered_bootstrap(df, statistic, level: float = 0.95, n_boot: int = 10_000):
    """Resample whole fixtures with replacement, not rows."""
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def weighted_regression(df, features: list[str]):
    """Turnover-weighted regression of ROI with fixture-clustered errors."""
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def sample_adequacy(turnover: float, n_fixtures: int, effect: float = 0.04) -> bool:
    """Can a slice this size resolve an effect of this magnitude at all?"""
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")
