"""Bet-behaviour features: the candidate patterns describing how the owner bet.

    OWNER MODULE — see CLAUDE.md -> Division of labour.
    Scaffolding only: signatures and contracts, no implementations.

Candidates (no verdicts until ``validate.py`` has run on the current data):

    log(stake)
    n_bets_on_position >= 2
    both_sides_flag
    is_under
    is_novelty_market
"""

from __future__ import annotations


def add_both_sides_flag(df):
    """Three-state flag: is both sides of one market on one fixture held?

    Group by ``event + event_day + market + market_type``
    (``loader.POSITION_KEY``) and inspect the selections in the group.

    **Not a boolean.** Many rows carry no ``selection`` — certain bookies
    never report a side for ``ah``, and ``1x2`` almost never carries one. When
    a position mixes known and unknown sides, a hedge cannot be ruled out.
    Recording those as False understates the flag; recording them as True
    invents a position.

    Decision table::

        both sides present among the known selections   -> "both"
        no unknown rows, but not both sides             -> "single"
        a single row in the position                    -> "single"
        >= 2 rows, at least one unknown side            -> "undetermined"

    Return a ``Categorical`` over ``{"both", "single", "undetermined"}``, not a
    nullable boolean. Verified on pandas 3.0.2: ``df[df.flag]``, ``.mean()``
    and ``groupby`` all drop ``pd.NA`` silently, so a nullable boolean would
    erase that turnover with no warning — the same class of silent
    coercion that pinning censored odds to 2.00 would be. A category has to be
    named to be selected.

    Downstream, convert to boolean deliberately at the regression boundary and
    run it both ways (undetermined excluded, then treated as False). If the
    coefficient does not move, the ambiguity is immaterial and that can be
    stated with evidence.

    Open: ``cs`` and ``score`` currently land in "undetermined",
    but have no complementary pair the way home/away and over/under do —
    arguably "single" by definition. ``1x2`` genuinely belongs in
    "undetermined". Owner's call.

    Report the turnover share of each state. Easy to get subtly wrong —
    ``tests/test_features.py`` already states the cases.
    """
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def add_n_bets_on_position(df):
    """Bets held on the same selection within a fixture-market group.

    Note the distinction from ``n_bets``, which counts individual bets
    aggregated into a single row.
    """
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def add_is_under(df):
    """Selection is ``under``."""
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def add_is_novelty_market(df):
    """Market type in ``loader.NOVELTY_MARKET_TYPES`` (``cs``, ``score``, ``custom``).

    Test it against the core types with stake size controlled for; the two
    are confounded.
    """
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")


def build_feature_frame(df):
    """Apply the candidate feature set in one pass, for the regression."""
    raise NotImplementedError("Owner module — see CLAUDE.md -> Division of labour")
