# sportmarket-analysis

Four years of personal sports betting history from Sportmarket Pro
(Nov 2022 – Sep 2026), and the machinery that decides which patterns in it are
real.

**The deliverable is a method, not a dashboard.** A set of candidate patterns
is put through the same skeptic battery, and every verdict — replicated,
insufficient, noise — is reported. A rejection produced by a working test is a
result, not an omission.

No results are published in this repository yet. Every figure must be computed
from the exports currently in `data/raw/` by the code in `src/`, with the
uncertainty the statistical rules below require.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"
cp /path/to/exports/*.csv data/raw/   # never committed
pytest -m "not owner"                 # tests for the modules that exist today
streamlit run app/streamlit_app.py
```

## Layout

```
data/raw/            Yearly CSV exports. Gitignored, always.
src/loader.py        CSV -> tidy frame. Normalisation, fixture ids, fill rate.
src/checks.py        Data-integrity battery. Reports, never repairs.
src/odds.py          Censoring-aware implied odds.            (owner)
src/features.py      both_sides_flag, n_bets_on_position, …   (owner)
src/stats.py         Fixture-clustered bootstrap, intervals.  (owner)
src/validate.py      The skeptic battery.                     (interface sketch)
tests/               Synthetic fixtures only; no real data.
app/streamlit_app.py Thin shell over the modules above.
reports/             Generated output. Gitignored.
```

## The five facts that break naive analysis

1. **A row is not a bet.** Each row aggregates `n_bets` individual bets on one
   selection. Row counts are not bet counts.
2. **`stake` is not `turnover`.** Analyse on `turnover`, and drop
   `turnover == 0` (`loader.matched`); those rows never matched.
3. **There are no bet timestamps.** `event_day` is the fixture date. Time-of-day
   and bet-order analysis is impossible, not merely hard.
4. **There is no line column.** The export says `over`, never `over 2.5`. A
   middle and a hedge are indistinguishable, so `both_sides_flag` is coarser
   than its name suggests.
5. **`selection` is absent on a material share of rows, and not at random.**
   It is fixed by market type, and within `ah` by bookie. Some market types
   live wholly among those rows, so filtering on completeness would silently
   remove them from the analysis. Absence is a category, not a defect.

## Data integrity

The facts above were established by hand once. `checks.py` makes them
re-runnable, so an export that breaks an assumption says so instead of quietly
changing the answer:

```python
df = loader.load_raw()
report = checks.run_checks(df)
print(report)
report.raise_if_errors()
```

Checks come in three severities. `ERROR` means the analysis would be
wrong (mixed currencies, `roi` disagreeing with `pl / turnover`, turnover above
the stake offered, a ratio the odds derivation cannot produce). `WARN` means a
human should look (an unrecognised market type, duplicate rows). `INFO` never
fails and carries the coverage figures so drift is visible at a glance.

It **reports and never repairs** — the same stance as `loader.py`, for the same
reason. Nothing here drops a row or fills a gap, because every silent repair
turns an "I don't know" into a number and the error becomes invisible.

## The censoring problem

Price-adjusted turnover encodes odds, but only below 2.00:

```
price_adjusted_turnover = turnover * min(1, odds - 1)
ratio  = price_adjusted_turnover / turnover
ratio < 0.999   ->  odds = 1 + ratio           exact
ratio >= 0.999  ->  odds >= 2.00               unknown, right-censored
```

The price-adjusted column is only populated in later years, so coverage
within those years and coverage across the whole dataset are very different
figures; both are reported by `checks.py`. Losing bets included. A censored
value is never the point estimate 2.00 — not in a mean, a bucket boundary, or
a regression feature. `implied_odds` returns `(odds, is_censored)` so the
caller has to decide, and censoring propagates through every downstream
aggregation.

## Statistical rules

1. Cluster on fixture (`event + event_day`) — always. Row-level standard errors
   badly understate uncertainty.
2. No point estimate without an interval. Enforced in the return type.
3. Threshold on fixture count, not turnover.
4. Correct for multiple comparisons and report how many hypotheses were tested.
   Scanning dozens of countries at 95% yields false positives by construction.
5. Out-of-sample replication is the gate, not in-sample significance.

## Candidate patterns

The hypotheses the machinery is built to test. None has a verdict until
`validate.py` has run on the current exports; all of them, including the
failures, go in the report.

- Behavioural: stake size, number of bets on a position, `both_sides_flag`,
  over vs under.
- Market: core vs novelty market types, differences among core market types.
- Segmentation: country, competition, bookie.
- Calendar / context: day of week, month, women's vs men's football,
  friendlies, league familiarity.

## Division of labour

This repo is also a way to learn data science, so some modules are written by
hand on purpose. `odds.py`, `features.py` and `stats.py` are the owner's —
assistants review, suggest and point out bugs there, but do not hand over
implementations. `tests/test_odds.py`, `test_features.py` and `test_stats.py`
state the contracts those modules must satisfy and are marked `owner`; they
fail until the modules exist, which is the intended workflow. See `CLAUDE.md`.

## Privacy

`Customer P/L` is personal financial information. `data/raw/` is gitignored. If
this repo is ever made public, index monetary values to a base of 100 or
rescale to a notional currency first. The method is what is on display.
