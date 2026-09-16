# sportmarket-analysis

A tool for analysing Sportmarket Pro betting exports: load them, check them,
explore performance by segment, and put candidate patterns through a skeptic
battery before calling any of them an edge.

It runs on two kinds of input:

- **A history.** Whatever exports are in `data/processed/` — for this repo, four
  years of the owner's own betting (Nov 2022 – Sep 2026), rescaled to notional
  units so the app can be run and shown without publishing the amounts.
- **A single file.** The Upload tab takes any Sportmarket Pro CSV, runs the same
  integrity battery on it, and reports how that file went. It is shown on its
  own and never merged into the loaded history.

No results are published in this repository. Every figure the app shows is
computed from the files currently under `data/`, by the code in `src/`, with the
uncertainty the statistical rules below require. Nothing is quoted from a
previous run.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"

cp /path/to/exports/*.csv data/raw/   # never committed
python src/loader.py                  # rewrites data/raw/ -> data/processed/ in units

pytest -m "not owner"                 # tests for the modules that exist today
streamlit run app/streamlit_app.py
```

The app reads `data/processed/` and nothing else. There is no toggle that shows
the raw amounts, and the raw files do not need to be on the machine the app runs
on — see [Units](#units). Skipping `python src/loader.py` leaves the app with
nothing to load, and it says so instead of falling back to `data/raw/`.

## The app

Four tabs over the modules in `src/`. A panel backed by a module that is not
written yet says so rather than inventing a number.

**Overview** — what is loaded: matched turnover, P/L, fill rate, odds coverage,
rows, bets, fixtures, unmatched rows, and cumulative P/L over time. Bucketed by
month, or by day when the loaded span is under a quarter, because a fresh export
bucketed monthly collapses to a single point.

**Upload** — check a new export. The file goes through the same loader and the
same integrity battery as the history does; a new export is worth nothing until
it passes the checks the old ones pass. Amounts can be read in units or in the
currency the file says it is in — nothing is converted, the label just follows
the file. Then: totals, how the file ran day by day (cumulative curve and signed
bars), and a breakdown by any of the dimensions below. One file covers a short
period, so every group in it is small; the captions say so, because a week of
betting cannot settle anything.

**Explore** — the segment explorer, and the part of the app that does the most
work. Filter on fixture date, stake range, market type and bookie; group by
market type, selection, bookie, country, competition, market, event type, stake
bucket, bets-per-row bucket, year, month or weekday; sort by turnover, ROI, P/L,
fixture count, bets per fixture or name; threshold on fixture count. Each slice
reports bets, fixtures, **bets per fixture**, turnover, P/L and turnover-weighted
ROI. Then a ROI bar chart of the largest slices, and a comparison of up to eight
slices over time on one set of axes — cumulative P/L, or cumulative ROI so that
slices of different size can be compared at all.

Two things the explorer insists on. Slices are aggregated with `dropna=False`,
so rows carrying no `selection` form their own visible category instead of
disappearing from every total that touches the column. And the table's caption
states how many slices are on screen and roughly how many of them would look
good by chance alone, so a slice standing out is never presented as a finding.

**Findings** — the candidate patterns, with a verdict each: it holds up, there is
too little data to tell, or it is noise. All verdicts are listed, failures
included. **The tests behind it are not written yet**, so every row currently
reads *not yet tested* and the tab is a queue rather than a result. See
[Status](#status).

Chart colours come from a validated palette: the diverging pair is blue↔red
rather than the conventional profit/loss red↔green, which is the pairing that
collapses under the commonest colour blindness. Eight categorical slots, checked
for contrast and colour-blind separation against this surface, are the hard
ceiling — hence the cap on the segment comparison.

## Layout

```
data/raw/            Exports as they come out of Sportmarket. Gitignored, always.
data/processed/       The same exports in units. Gitignored. What the app reads.
src/loader.py         CSV -> tidy frame; fixture ids; fill rate; the units rewrite.
src/checks.py         Data-integrity battery. Reports, never repairs.
src/odds.py           Censoring-aware implied odds.            (owner, not written)
src/features.py       both_sides_flag, n_bets_on_position, …   (owner, not written)
src/stats.py          Fixture-clustered bootstrap, intervals.  (owner, not written)
src/validate.py       The skeptic battery.                     (interface sketch)
app/streamlit_app.py  The four tabs above.
.streamlit/           Theme; one accent colour shared with the app's palette.
tests/                Synthetic fixtures only; no real data.
reports/              Generated output. Gitignored.
```

## What the export format actually says

Five facts that break a naive reading. The app is built around them; the checks
make them re-runnable.

1. **A row is not a bet.** Each row aggregates `n_bets` individual bets on one
   selection. Row counts are not bet counts, and bets on one fixture win or lose
   together — which is why every table reports bets per fixture.
2. **`stake` is not `turnover`.** Analyse on `turnover`, and drop
   `turnover == 0` (`loader.matched`); those rows never matched.
3. **There are no bet timestamps.** `event_day` is the fixture date. Time-of-day
   and bet-order analysis is impossible, not merely hard.
4. **There is no line column.** The export says `over`, never `over 2.5`. A
   middle and a hedge are indistinguishable, so `both_sides_flag` is coarser
   than its name suggests.
5. **`selection` is absent on a material share of rows, and not at random.** It
   is fixed by market type, and within `ah` by bookie. Some market types live
   wholly among those rows, so filtering on completeness would silently remove
   them from the analysis. Absence is a category, not a defect.

## Data integrity

The facts above were established by hand once. `checks.py` makes them
re-runnable, so an export that breaks an assumption says so instead of quietly
changing the answer:

```python
df = loader.load_raw(loader.DEFAULT_PROCESSED_DIR)
report = checks.run_checks(df)
print(report)
report.raise_if_errors()
```

The app runs this on every load, for the history and for an upload alike. Green
checks are silent behind an expander; a failure is a banner above every tab,
because no figure below it can be trusted.

Three severities. `ERROR` means the analysis would be wrong (mixed currencies,
`roi` disagreeing with `pl / turnover`, turnover above the stake offered, a ratio
the odds derivation cannot produce). `WARN` means a human should look (an
unrecognised market type, duplicate rows). `INFO` never fails and carries the
coverage figures so drift is visible at a glance.

It **reports and never repairs** — the same stance as `loader.py`, for the same
reason. Nothing drops a row or fills a gap, because every silent repair turns an
"I don't know" into a number and makes the error invisible.

## The censoring problem

Price-adjusted turnover encodes odds, but only below 2.00:

```
price_adjusted_turnover = turnover * min(1, odds - 1)
ratio  = price_adjusted_turnover / turnover
ratio < 0.999   ->  odds = 1 + ratio           exact
ratio >= 0.999  ->  odds >= 2.00               unknown, right-censored
```

The column is only populated in later years, so coverage within those years and
coverage across the whole dataset are very different figures; both are reported
by `checks.py`, and the Overview's odds-coverage metric is the whole-dataset one.
Losing bets are covered too.

A censored value is never the point estimate 2.00 — not in a mean, a bucket
boundary, or a regression feature. `implied_odds` returns `(odds, is_censored)`
so the caller has to decide, and censoring propagates through every downstream
aggregation. This derivation was reverse-engineered on an earlier export and is
the most fragile piece of domain knowledge here; re-verify it against the
current files before relying on it.

## Statistical rules

The contract `stats.py` and `validate.py` must satisfy. They are not style
preferences — violating them invalidates the analysis.

1. Cluster on fixture (`event + event_day`) — always. Row-level standard errors
   badly understate uncertainty.
2. No point estimate without an interval. Enforced in the return type.
3. Threshold on fixture count, not turnover.
4. Correct for multiple comparisons and report how many hypotheses were tested.
   Scanning dozens of countries at 95% yields false positives by construction.
5. Out-of-sample replication is the gate, not in-sample significance.

Until those modules exist, the explorer deliberately stops short of a verdict:
it shows point estimates with the fixture counts behind them and says plainly
how many slices are on screen. A number on the Explore tab is a description of
what happened, never a claim that it will happen again.

## Candidate patterns

The hypotheses the machinery is built to test, listed on the Findings tab. None
has a verdict until `validate.py` runs; all of them, failures included, go in
the report.

- Behavioural: stake size, number of bets on a position, `both_sides_flag`,
  over vs under.
- Market: core vs novelty market types, differences among core market types.
- Segmentation: country, competition, bookie.
- Calendar / context: day of week, month, women's vs men's football,
  friendlies, league familiarity.

## Status

| Part | State |
| --- | --- |
| `loader.py`, `checks.py` | Written and tested. |
| Overview, Upload, Explore | Working on real exports. |
| `odds.py`, `features.py`, `stats.py` | Signatures and contracts only; every function raises. |
| `validate.py` | Interface proposal, open questions in the module docstring. |
| Findings | Queue of hypotheses; no verdicts until the above are written. |

`tests/test_odds.py`, `test_features.py` and `test_stats.py` state the contracts
the unwritten modules must satisfy and are marked `owner`. They fail until those
modules exist, which is the intended workflow — `pytest -m "not owner"` is the
suite that should be green.

## Units

`Customer P/L` is personal financial information, and the app is meant to be
runnable in front of someone. So the amounts it reads are not currency.

`python src/loader.py` divides every monetary column of every export by one
constant — by default the median matched stake, so `1 unit` reads as one typical
bet — relabels the currency column `units`, and writes the result to
`data/processed/`. The constant is printed to the terminal and stored nowhere, so
the processed files cannot be scaled back, and they can be deployed without the
raw ones. Pass `--unit` to set it yourself.

Dividing by a constant leaves ROI, fill rate, the odds ratio and every integrity
check untouched, so nothing downstream needs to know it happened. The processed
files keep the export's own headers and every non-monetary column byte for byte,
and therefore go through the same loader, the same checks and the same upload
path as a raw export.

Both `data/raw/` and `data/processed/` are gitignored, as is `reports/`. There is
no toggle back to currency for the loaded history; someone who uploads their own
export chooses units or currency for that file alone, and it is held in memory
for that session only. The method is what is on display, not the amounts.

## Division of labour

This repo is also a way to learn data science, so some modules are written by
hand on purpose. `odds.py`, `features.py` and `stats.py` are the owner's —
assistants review, suggest and point out bugs there, but do not hand over
implementations. `validate.py` is a grey area: sketch the interface together
first. Everything else — scaffolding, `loader.py`, `checks.py`, the app, this
README, linting — is fair game. See `CLAUDE.md`.
