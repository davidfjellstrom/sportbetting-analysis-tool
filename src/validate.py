"""The skeptic battery: does a proposed segmentation survive, or is it noise?

    GREY AREA — CLAUDE.md says to sketch this interface together first.
    What follows is a proposal, not an agreed design. Argue with it before
    anything gets implemented.

Most candidate patterns are expected to turn out to be noise. This module is
what does the rejecting, so it is the actual deliverable. Its job is to make
the verdict boring and repeatable rather than a judgement call:

* clustered CI per slice (``stats.clustered_bootstrap``)
* permutation test of the slice spread against chance
* multiple-comparison correction — scanning dozens of countries at 95%
  produces false positives by construction, so the count of hypotheses is
  part of the output, not a footnote
* out-of-sample replication as the gate, not in-sample significance

Prefer walk-forward validation over a single split where the data allows.

Open questions to settle first:
  - Does ``SegmentReport`` carry per-slice rows, or a frame plus a verdict?
  - Is the build/test split a parameter, or fixed at 2022–24 / 2025–26?
  - Which correction: Bonferroni, or Benjamini–Hochberg on the scan?
  - What separates INSUFFICIENT from NOISE — adequacy only, or CI width too?
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Verdict(StrEnum):
    REPLICATES = "REPLICATES"
    INSUFFICIENT = "INSUFFICIENT"
    NOISE = "NOISE"


@dataclass(frozen=True)
class SegmentReport:
    """Proposed shape — fields to be agreed before implementing.

    Sketch: ``column``, ``verdict``, ``n_slices_tested``, ``per_slice`` (a frame
    of estimate + CI + fixture count per level), ``oos_correlation``,
    ``oos_p_value``, ``correction``, ``notes``.
    """


def evaluate_segmentation(df, column: str, min_fixtures: int = 200) -> SegmentReport:
    """Run the full battery on a proposed segmentation and return a verdict.

    ``min_fixtures`` thresholds on fixture count rather than turnover on
    purpose: 10,000 EUR across 100 fixtures is far noisier than the same amount
    across 400, and turnover hides that.
    """
    raise NotImplementedError("Interface not agreed yet — see module docstring")


def walk_forward(df, column: str, folds: int = 4):
    """Repeat the build/test evaluation across rolling windows."""
    raise NotImplementedError("Interface not agreed yet — see module docstring")
