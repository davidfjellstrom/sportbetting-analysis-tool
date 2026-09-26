import { useEffect, useMemo, useState } from 'react'
import type {
  CompareRules,
  DimensionKey,
  ExploreOptions,
  ExploreQuery,
  ExploreResponse,
  SortKey,
} from '../api/types'
import { compareSpec, measureLabel, type Measure } from '../charts/compare'
import { cumulativeSpec } from '../charts/cumulative'
import { plBarsSpec } from '../charts/plBars'
import { roiBarsSpec } from '../charts/roiBars'
import { Alert } from '../components/Alert'
import { Help } from '../components/Help'
import { LazyChart } from '../components/LazyChart'
import { Metric, MetricRow } from '../components/Metric'
import { MultiSelect } from '../components/MultiSelect'
import { NumberField } from '../components/NumberField'
import { Select } from '../components/Select'
import { SliceTable } from '../components/SliceTable'
import { UNKNOWN, fixed, integer, money, signed } from '../format'
import { exploreQuery, type ExploreState } from './exploreState'

// "at least 28 units staked and 20 matches": the bars a group must clear.
function curveBars(rules: CompareRules, cur: string): string {
  const bars = [`${fixed(rules.min_turnover)} ${cur} staked`]
  if (rules.min_bets !== null) bars.push(`${integer(rules.min_bets)} bets`)
  if (rules.min_fixtures !== null) bars.push(`${integer(rules.min_fixtures)} matches`)
  return `at least ${bars.join(' and ')}`
}

interface Result {
  key: string
  response: ExploreResponse
}

export function Explore({
  state,
  setState,
  options,
  fetchExplore,
}: {
  state: ExploreState
  setState: (update: (s: ExploreState) => ExploreState) => void
  options: ExploreOptions
  /** Where the answers come from: the history, or an uploaded file. */
  fetchExplore: (query: ExploreQuery) => Promise<ExploreResponse>
}) {
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState<string | null>(null)
  const queryKey = JSON.stringify(exploreQuery(state))

  useEffect(() => {
    let cancelled = false
    fetchExplore(JSON.parse(queryKey))
      .then((response) => {
        if (cancelled) return
        setError(null)
        setResult({ key: queryKey, response })
        if (response.status === 'ok') {
          const forKey = response.eligible.join('\u0000')
          setState((s) =>
            s.pickedFor === forKey
              ? s
              : { ...s, picked: response.eligible.slice(0, 3), pickedFor: forKey },
          )
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(String(e))
      })
    return () => {
      cancelled = true
    }
  }, [queryKey, setState, fetchExplore])

  const cur = options.currency
  const response = result?.response
  const ok = response?.status === 'ok' ? response : null
  const dimension = options.dimensions.find((d) => d.key === state.groupBy) ?? {
    key: state.groupBy,
    label: state.groupBy,
  }
  const dimensionLabel = dimension.label

  const barRows = useMemo(() => {
    if (!ok) return []
    const byName = new Map(ok.table.map((r) => [r.slice, r]))
    return ok.bars_order
      .slice(0, Math.min(state.topN, ok.table.length))
      .map((name) => byName.get(name)!)
  }, [ok, state.topN])
  const barOrder = useMemo(() => barRows.map((r) => r.slice), [barRows])
  const barsSpec = useMemo(
    () => (ok ? roiBarsSpec(barRows, barOrder, dimensionLabel, cur) : null),
    [ok, barRows, barOrder, dimensionLabel, cur],
  )
  const compare = useMemo(
    () =>
      ok && state.picked.length
        ? compareSpec(
            ok.curves,
            state.picked,
            state.measure,
            dimensionLabel,
            cur,
            ok.curve_bucket,
          )
        : null,
    [ok, state.picked, state.measure, dimensionLabel, cur],
  )

  // An uploaded file's running P/L, following the filters. The history's is
  // on the Overview tab, so the API leaves it out here.
  const overTime = useMemo(
    () =>
      ok?.cumulative
        ? {
            curve: cumulativeSpec(ok.cumulative, cur),
            bars: plBarsSpec(ok.cumulative, cur),
          }
        : null,
    [ok, cur],
  )

  const stale = result !== null && result.key !== queryKey
  const { max_series } = options.compare
  const bars = curveBars(options.compare, cur)
  const hasStake = options.stake_ceiling !== null && state.maxStake !== null

  return (
    <>
      <details className="expander" open>
        <summary>Filters</summary>
        <div className="controls filters-row-1">
          <div className="control">
            <span className="label">Match date range</span>
            <div className="date-range">
              <input
                type="date"
                value={state.dateFrom}
                min={options.date_min}
                max={state.dateTo}
                onChange={(e) => {
                  const v = e.target.value
                  if (v) setState((s) => ({ ...s, dateFrom: v }))
                }}
              />
              <span aria-hidden="true">–</span>
              <input
                type="date"
                value={state.dateTo}
                min={state.dateFrom}
                max={options.date_max}
                onChange={(e) => {
                  const v = e.target.value
                  if (v) setState((s) => ({ ...s, dateTo: v }))
                }}
              />
            </div>
          </div>
          {hasStake && (
            <>
              <NumberField
                label={`Minimum stake (${cur})`}
                value={state.minStake}
                min={0}
                step={0.5}
                onCommit={(v) => setState((s) => ({ ...s, minStake: v }))}
              />
              <NumberField
                label={`Maximum stake (${cur})`}
                value={state.maxStake!}
                min={0}
                step={0.5}
                help={`Starts at the largest stake in the data (${fixed(options.stake_ceiling!)}).`}
                onCommit={(v) => setState((s) => ({ ...s, maxStake: v }))}
              />
            </>
          )}
        </div>
        {/* A filter whose column the data lacks is left out, not shown empty. */}
        {(options.market_types.length > 0 || options.bookies.length > 0) && (
          <div className="controls two">
            {options.market_types.length > 0 && (
              <MultiSelect
                label="Market type"
                options={options.market_types}
                selected={state.marketTypes}
                onChange={(v) => setState((s) => ({ ...s, marketTypes: v }))}
              />
            )}
            {options.bookies.length > 0 && (
              <MultiSelect
                label="Bookie"
                options={options.bookies}
                selected={state.bookies}
                onChange={(v) => setState((s) => ({ ...s, bookies: v }))}
              />
            )}
          </div>
        )}
      </details>

      {error && (
        <Alert kind="error" icon="🚨">
          Could not reach the API: {error}
        </Alert>
      )}
      {!response && !error && <div className="loading">Loading…</div>}

      {response && response.status !== 'ok' && (
        <Alert kind="warning">{response.message}</Alert>
      )}

      {ok && barsSpec && (
        <div className={stale ? 'stale' : undefined}>
          <MetricRow>
            <Metric label={`Turnover in view (${cur})`} value={money(ok.view.turnover, cur)} />
            <Metric label={`P/L in view (${cur})`} value={money(ok.view.pl, cur, true)} />
            <Metric label="ROI in view" value={`${signed(ok.view.roi_pct, 2)}%`} />
            <Metric
              label="Bets in view"
              value={ok.view.bets === null ? UNKNOWN : integer(ok.view.bets)}
            />
            <Metric label="Matches in view" value={integer(ok.view.fixtures)} />
          </MetricRow>

          {overTime && (
            <>
              <h3 className="accent">How this file ran ({cur})</h3>
              <LazyChart spec={overTime.curve} height={320} />
              <LazyChart spec={overTime.bars} height={260} />
              <p className="caption">
                A few good or bad days in a row is normal — a coin flip does the same.
              </p>
            </>
          )}

          <div className="controls group-row">
            <label className="control">
              <span className="label">Group by</span>
              <Select
                value={state.groupBy}
                onChange={(v) => setState((s) => ({ ...s, groupBy: v as DimensionKey }))}
                options={options.dimensions.map((d) => ({ value: d.key, label: d.label }))}
              />
            </label>
            <label className="control">
              <span className="label">Sort by</span>
              <Select
                value={state.sort}
                onChange={(v) => setState((s) => ({ ...s, sort: v as SortKey }))}
                options={options.sorts.map((o) => ({ value: o.key, label: o.label }))}
              />
            </label>
            <NumberField
              label="Min. matches"
              value={state.minFixtures}
              min={0}
              step={25}
              onCommit={(v) => setState((s) => ({ ...s, minFixtures: Math.round(v) }))}
            />
          </div>

          <p className="caption">
            {ok.groups_shown} of {ok.groups_total} groups shown
          </p>
          <SliceTable rows={ok.table} dimension={dimension} currency={cur} />
          {overTime && (
            <p className="caption">
              One file covers a short period, so each group is small. Check the number of
              matches before reading anything into the ROI.
            </p>
          )}

          <label className="control slider">
            <span className="label">Groups to chart (largest first)</span>
            <div className="slider-row">
              <input
                type="range"
                min={3}
                max={40}
                step={1}
                value={state.topN}
                onChange={(e) => setState((s) => ({ ...s, topN: Number(e.target.value) }))}
              />
              <span className="slider-value">{state.topN}</span>
            </div>
          </label>
          <LazyChart spec={barsSpec} height={340} />

          <h3 className="accent">Compare segments over time</h3>
          {ok.eligible.length === 0 ? (
            <Alert kind="info" icon="🔍">
              No group here is big enough to chart ({bars}). Try another grouping or wider
              filters.
            </Alert>
          ) : (
            <>
              <div className="controls pick-row">
                <MultiSelect
                  label="Groups to compare"
                  options={ok.eligible}
                  selected={state.picked}
                  max={max_series}
                  help={`Only groups with ${bars} are listed (${ok.eligible.length} of ${ok.groups_total}). Up to ${max_series} at a time so the colours stay apart.`}
                  onChange={(v) => setState((s) => ({ ...s, picked: v }))}
                />
                <fieldset className="control">
                  <legend className="label">
                    Measure{' '}
                    <Help text="P/L favours big groups — more bets, more profit. ROI shows the return on what was staked, so groups of any size can be compared." />
                  </legend>
                  <div className="radio-col">
                    {(['cum_pl', 'cum_roi_pct'] as Measure[]).map((m) => (
                      <label key={m} className="radio">
                        <input
                          type="radio"
                          name="measure"
                          value={m}
                          checked={state.measure === m}
                          onChange={() => setState((s) => ({ ...s, measure: m }))}
                        />
                        {measureLabel(m, cur)}
                      </label>
                    ))}
                  </div>
                </fieldset>
              </div>
              {compare ? (
                <>
                  <LazyChart spec={compare} height={380} />
                  <p className="caption">
                    ROI swings a lot at the start, when only a few bets have been placed.
                    That settles as the bets add up.
                  </p>
                </>
              ) : (
                <Alert kind="info" icon="👆">
                  Pick at least one group.
                </Alert>
              )}
            </>
          )}
        </div>
      )}
    </>
  )
}
