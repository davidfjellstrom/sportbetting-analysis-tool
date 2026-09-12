# CLAUDE.md — sportmarket-analysis

Read this before writing or modifying any code in this repo.

## What this project is

An analysis of ~4 years of personal sports betting history exported from
Sportmarket Pro (Nov 2022 – Sep 2026).

**The deliverable is a method, not a dashboard.** The interesting result is not
"here are patterns in the data" — it is "here are N candidate patterns, here is
the machinery that tested them, and most turned out to be noise." Findings that
are rejected are content, not failure. Do not quietly drop them from the report.

**Nothing is established yet.** This file deliberately contains no numbers
from the data. Every figure — turnover, yield, coverage, share of missing
values, which segments replicate — must be computed from the exports currently
in `data/raw/` by the code in `src/`, and reported with the uncertainty the
statistical rules below require. Do not quote results from memory or from
earlier sessions; the raw files change.

Secondary goal: the repo owner is learning data science. See
[Division of labour](#division-of-labour) — some modules are deliberately not
yours to write.

## The data

CSVs in `data/raw/`, one per year, same schema. **Never commit these.**

| Column | Meaning |
| --- | --- |
| `Event` | "Team A v Team B" |
| `Market` | Sport and period, **not** the market description: `Football`, `Football (Half Time)`, `Football (Corners)`, … |
| `Market Type` | Core `ah`, `ahou`, `ou`, `1x2`, `taou`; novelty `cs`, `score`, `custom`; plus a long tail of rare others (`other`, `ml`, `gr`, `props`, …) |
| `Selection` | `home`, `away`, `over`, `under`, `draw` — **or absent.** Read as NaN (the export writes `n/a`). See below |
| `Country`, `Competition`, `Event Type` | Categorisation of the fixture |
| `Bookie` | Which book the broker routed to. Also contains `cashout` as a pseudo-book |
| `Event Day` | Date of the fixture, **not** the date the bet was placed |
| `Nr of Bets` | Number of individual bets aggregated into this row |
| `Stake` | Intended stake |
| `Customer turnover` | Actually matched stake. `0` means fully unmatched |
| `Customer price adjusted turnover` | See below. Column present in every file but only populated in later years |
| `Customer currency` | Expected to be `EUR` throughout. Dropped by the loader; a non-EUR row would silently mix currencies, so `checks.py` guards it |
| `Customer P/L` | Profit or loss in EUR |
| `ROI` | `P/L / turnover` |

### Critical facts about the schema

**A row is not a bet.** It is an aggregate of `Nr of Bets` individual bets on
the same selection. Row counts are not bet counts.

**`Stake` is not `Customer turnover`.** Always analyse on `Customer turnover`.
Rows with `Customer turnover == 0` are unmatched and must be excluded from
every performance calculation. `ROI` is NaN on exactly those rows. Report the
fill rate and the unmatched share; do not assume them.

**There are no bet timestamps.** `Event Day` is the fixture date. Any
time-of-day or bet-placement-order analysis is impossible. Do not fake it.

**There is no line or handicap column.** The export records that a bet was
`over`, not that it was over 2.5. Two bets on the same fixture and market type
cannot be told apart by line, so "over 2.5 plus under 3.5" (a middle) is
indistinguishable from "over 2.5 plus under 2.5" (a hedge). This is a limit of
the source data, not of the code — `both_sides_flag` is coarser than its name
suggests and the README must say so.

**`Selection` is absent on a material share of rows, and not at random.**
For novelty types (`cs`, `score`, `custom`, …) and `1x2` there is usually no
side to record. For `ah` the missing side appears to be a bookie × market-type
recording artifact rather than a property of the bet — verify this on the
current data (check whether the same books report a side on `ou`/`ahou`/`taou`,
and compare odds and stake distributions with and without a side).

Rows without a side may perform differently from rows with one, and some
market types live wholly among them. **Never filter on completeness; treat
absence as a category.** Any analysis that drops these rows must say so and
report what it dropped.

## The price-adjusted-turnover derivation

This was reverse-engineered empirically on an earlier export and is the single
most fragile piece of domain knowledge in the repo. It belongs in
`src/odds.py`. **Re-verify it on the current data before relying on it.**

```
price_adjusted_turnover = turnover * min(1, odds - 1)
```

Therefore:

- `ratio = pat / turnover`
- If `ratio < 0.999` → `odds = 1 + ratio`, **exact**.
- If `ratio >= 0.999` → odds were >= 2.00 and the true value is **unknown**.
  This is right-censoring.

How to verify: among winning single-bet rows with `ratio < 1`, realised ROI
should equal `ratio`; among those with `ratio ≈ 1`, ROI should be >= ~1 with a
long right tail; derived odds should never materially exceed 2.00.

Coverage is conditional: the column is only populated in later years, so
whole-dataset coverage is far lower than coverage within the populated years.
Compute and report both. Any odds-based analysis is a separate, smaller study
on the covered subset — not a variable available to the main analysis. The
derivation applies to **losing bets too**, not only winners.

### Non-negotiable rule

**A censored odds value must never be used as the point estimate 2.00.**
Not in a mean, not in a bucket boundary, not in a regression feature. The
public API must make this hard to get wrong:

```python
def implied_odds(turnover, price_adjusted_turnover) -> tuple[float | None, bool]:
    """Returns (odds, is_censored). When is_censored is True, odds is None
    and the caller must handle the >= 2.00 case explicitly."""
```

Censoring must propagate through every downstream aggregation. If a function
cannot handle censored input, it should raise, not silently coerce.

## Statistical rules

These are not style preferences. Violating them invalidates the analysis.

1. **Cluster on fixture, always.** The clustering unit is `Event + Event Day`.
   Rows within the same fixture are correlated — the owner routinely places
   several bets on one match. Row-level standard errors are wrong and badly
   understate uncertainty.

2. **No point estimate without an interval.** No function in `stats.py` may
   return a yield, ROI or edge without an accompanying confidence interval.
   Enforce this in the return type.

3. **Threshold on fixture count, not turnover.** Because of clustering, a slice
   with 10,000 EUR across 100 fixtures is far noisier than the same amount
   across 400. Turnover hides this.

4. **Correct for multiple comparisons.** Scanning dozens of countries at the
   95% level yields false positives by construction. Any segmentation scan
   must report how many hypotheses were tested.

5. **Out-of-sample replication is the gate**, not statistical significance in
   the full sample. Build on an early window, test on a later one.

## Candidate patterns

These are the hypotheses the machinery is built to test. None has a verdict
until `validate.py` has run on the current exports. List them all in the
report, with verdicts, including the ones that fail.

- Behavioural: stake size, number of bets on a position, `both_sides_flag`,
  over vs under.
- Market: core vs novelty market types, differences among core market types.
- Segmentation: country, competition, bookie.
- Calendar / context: day of week, month, women's vs men's football,
  friendlies, league familiarity.

## Division of labour

The owner is building this to learn. Respect the boundary.

**You may write:** repo scaffolding, `loader.py`, test harness setup, the
Streamlit app in `app/`, README structure, linting config.

**You must not write unprompted:** `odds.py`, `features.py`, `stats.py`. These
contain the censoring logic, the `both_sides_flag` grouping and the clustered
bootstrap — the parts worth struggling with. Offer design feedback, review
code, suggest approaches, point out bugs. Do not hand over finished
implementations unless explicitly asked.

`validate.py` is a grey area. Sketch the interface together first.

## Implementation notes

`both_sides_flag` is **not a boolean.** Group by
`Event + Event Day + Market + Market Type` and inspect the selections held.
Because many rows carry no side, a position that mixes known and unknown
sides cannot be resolved either way — recording it False understates the flag,
recording it True invents a position. Three states, as a `Categorical`:

| Condition | State |
| --- | --- |
| Both sides present among the known selections | `both` |
| No unknown rows, but not both sides | `single` |
| A single row in the position | `single` — one row cannot be two sides |
| >= 2 rows, at least one with an unknown side | `undetermined` |

Report the turnover share of each state; expect `undetermined` to be
concentrated in `ah` and `1x2`.

Do not use a nullable boolean. Verified on pandas 3.0.2: `df[df.flag]`,
`.mean()` and `groupby` all drop `pd.NA` silently, so the `undetermined` rows
would vanish without warning — the same class of silent coercion as pinning
censored odds to 2.00. A category has to be named to be selected.

Convert to boolean deliberately at the regression boundary, and run it both
ways (undetermined excluded, then treated as False). If the coefficient does
not move, the ambiguity is immaterial and can be reported as such.

Open question: `cs` and `score` currently fall in `undetermined` but have no
complementary pair the way home/away and over/under do — arguably `single` by
definition. `1x2` genuinely belongs in `undetermined`.

Easy to get subtly wrong. Write a test for it, including a case with a missing
side — `tests/conftest.py` has no such row today.

`validate.py` should expose something like:

```python
def evaluate_segmentation(df, column, min_fixtures=200) -> SegmentReport:
    """Runs the full skeptic battery on a proposed segmentation:
    clustered CI per slice, permutation test against chance,
    multiple-comparison correction, out-of-sample replication.
    Verdict: REPLICATES / INSUFFICIENT / NOISE."""
```

Prefer walk-forward validation over a single split where feasible.

## Privacy

`Customer P/L` is personal financial information. If this repo goes public,
index all monetary values to a base of 100 or rescale to a notional currency,
and keep `data/raw/` in `.gitignore`. The method is what is on display, not the
amounts.
