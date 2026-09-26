import { useMemo, useState } from 'react'
import type { UploadChoice } from '../api/client'
import type { DimensionKey, UploadResponse } from '../api/types'
import { currencyOptions, type UploadState } from './uploadState'
import { cumulativeSpec } from '../charts/cumulative'
import { plBarsSpec } from '../charts/plBars'
import { Alert } from '../components/Alert'
import { CheckFailureBanner, CheckTable } from '../components/CheckReport'
import { Help } from '../components/Help'
import { LazyChart } from '../components/LazyChart'
import { Metric, MetricRow } from '../components/Metric'
import { Select } from '../components/Select'
import { SliceTable } from '../components/SliceTable'
import { UNKNOWN, integer, money, percent } from '../format'

// "A", "A or B", "A, B or C": the missing columns, read as a sentence.
function listed(items: string[]): string {
  return items.length < 2
    ? items.join('')
    : `${items.slice(0, -1).join(', ')} or ${items[items.length - 1]}`
}

// The file's own dimensions: a column the export left out has no dimension,
// so a choice carried over from an earlier file may not exist here.
function groupByFor(result: UploadResponse, wanted: DimensionKey): DimensionKey {
  const keys = result.dimensions.map((d) => d.key as DimensionKey)
  return keys.includes(wanted) ? wanted : keys[0]
}

export function Upload({
  state,
  setState,
  onCheck,
  onRemove,
}: {
  state: UploadState
  setState: (update: (s: UploadState) => UploadState) => void
  /** Check a file, or the same file again with a new unit or currency. */
  onCheck: (file: File, choice?: UploadChoice) => void
  /** Forget the file, here and in this browser's storage. */
  onRemove: () => void
}) {
  const [unitDraft, setUnitDraft] = useState<string | null>(null)

  function commitUnit() {
    if (unitDraft === null) return
    const value = Number(unitDraft)
    setUnitDraft(null)
    if (!Number.isFinite(value) || value < 0.01) return
    if (value.toFixed(2) === state.unitText) return
    if (state.file) onCheck(state.file, { unit: value, currency: state.chosenCurrency })
  }

  const result = state.status === 'done' || state.status === 'checking' ? state.result : undefined
  const cur = state.display === 'Units' ? 'units' : state.chosenCurrency
  // A unit is a stake in the file's own currency, whatever it is shown in.
  const fileCur = result?.file.currency_in_file ?? 'EUR'
  const fx = result?.file.fx
  const view = result ? (state.display === 'Units' ? result.units : result.currency) : undefined
  const cumulative = useMemo(
    () => (view ? cumulativeSpec(view.cumulative, cur) : null),
    [view, cur],
  )
  const bars = useMemo(() => (view ? plBarsSpec(view.cumulative, cur) : null), [view, cur])
  const groupBy = result ? groupByFor(result, state.groupBy) : state.groupBy
  const dimensionLabel =
    result?.dimensions.find((d) => d.key === groupBy)?.label ?? groupBy

  return (
    <>
      <h3 className="accent">Check a new export</h3>
      <p className="caption">Upload your own Sportmarket Pro CSV-export to get it analyzed.</p>

      <label className="uploader">
        <span className="label">Sportmarket Pro export (CSV)</span>
        {/* The browser's own file input is invisible but covers the box, so a
            click or a drop still reaches it. Its own "no file chosen" text is
            wrong whenever the file was restored from this browser's storage. */}
        <span className="uploader-box">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) onCheck(file)
              // Let the same file be chosen again after it was removed.
              e.target.value = ''
            }}
          />
          <span className="uploader-button">Choose file</span>
          <span className="uploader-name">
            {state.file ? state.file.name : 'or drag a CSV file here'}
          </span>
        </span>
      </label>
      {state.file && (
        <div className="uploader-actions">
          <span className="caption">
            Kept in this browser for 24 hours, so a reload does not lose it. Explore
            shows this file until you remove it.
          </span>
          <button type="button" className="button-secondary" onClick={onRemove}>
            Remove file
          </button>
        </div>
      )}

      {state.status === 'idle' && (
        <Alert kind="info" icon="📄">
          No file loaded.
        </Alert>
      )}
      {state.status === 'error' && (
        <Alert kind="error" icon="🚨">
          {state.error}
        </Alert>
      )}
      {state.status === 'done' && state.error && (
        <Alert kind="warning" icon="⚠️">
          {state.error}
        </Alert>
      )}
      {state.status === 'checking' && !result && <div className="loading">Checking…</div>}

      {result && view && cumulative && bars && (
        <>
          {/* Silent when the checks pass, as for the history: a user has no use
              for a list of green ticks. A failure still stops them, because no
              figure below it can be trusted. */}
          {!result.checks.ok && (
            <>
              <CheckFailureBanner report={result.checks} />
              <CheckTable report={result.checks} />
            </>
          )}

          {result.missing_columns.length > 0 && (
            <Alert kind="info" icon="🧩">
              For your information, this file has no {listed(result.missing_columns)}{' '}
              {result.missing_columns.length > 1 ? 'columns' : 'column'} — add{' '}
              {result.missing_columns.length > 1 ? 'them' : 'it'} to your export to get
              the most out of the tool.
            </Alert>
          )}

          <div className="controls three">
            <fieldset className="control">
              <legend className="label">Show amounts in</legend>
              <div className="radio-row">
                {(['Units', 'Currency'] as const).map((option) => (
                  <label key={option} className="radio">
                    <input
                      type="radio"
                      name="display"
                      value={option}
                      checked={state.display === option}
                      onChange={() => setState((s) => ({ ...s, display: option }))}
                    />
                    {option}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="control">
              <span className="label">
                Currency{' '}
                <Help text={`Your file's amounts are in ${fileCur}. Pick another currency to convert them at today's exchange rate from the European Central Bank.`} />
              </span>
              <Select
                value={state.chosenCurrency}
                onChange={(v) => {
                  if (state.file && v !== state.chosenCurrency) {
                    onCheck(state.file, { unit: Number(state.unitText), currency: v })
                  }
                }}
                options={currencyOptions(result).map((c) => ({ value: c, label: c }))}
              />
            </label>
            <label className="control">
              <span className="label">
                1 unit = ({fileCur}){' '}
                <Help text="Your typical stake in this file, unless you set another." />
              </span>
              <input
                type="number"
                min={0.01}
                step={1}
                disabled={state.display !== 'Units'}
                value={unitDraft ?? state.unitText}
                onChange={(e) => setUnitDraft(e.target.value)}
                onBlur={commitUnit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                }}
              />
            </label>
          </div>

          <MetricRow>
            <Metric label={`Matched turnover (${cur})`} value={money(view.matched.turnover, cur)} />
            <Metric label={`P/L (${cur})`} value={money(view.matched.pl, cur, 0, true)} />
            <Metric
              label="Bets"
              value={result.report.n_bets === null ? UNKNOWN : integer(result.report.n_bets)}
            />
            <Metric label="Matches" value={integer(result.report.n_fixtures)} />
          </MetricRow>
          {state.display === 'Currency' && fx && (
            <p className="caption">
              Converted from {fx.base} at 1 {fx.base} = {fx.rate} {fx.target}.
            </p>
          )}
          <p className="caption">
            {integer(result.report.n_rows)} rows, {result.report.date_min} to{' '}
            {result.report.date_max}. {integer(result.report.n_unmatched_rows)} row(s) (
            {percent(result.report.unmatched_row_share)}) never got matched and are left
            out of the figures above.
          </p>

          <h3 className="accent">How this file ran ({cur})</h3>
          <LazyChart spec={cumulative} height={320} />
          <LazyChart spec={bars} height={260} />
          <p className="caption">
            Shown per day for short files, per month for longer ones. A few good or bad
            days in a row is normal — a coin flip does the same.
          </p>

          <h3 className="accent">Breakdown</h3>
          <label className="control">
            <span className="label">Group by</span>
            <Select
              value={groupBy}
              onChange={(v) => setState((s) => ({ ...s, groupBy: v as DimensionKey }))}
              options={result.dimensions.map((d) => ({ value: d.key, label: d.label }))}
            />
          </label>
          <SliceTable
            rows={view.breakdown[groupBy] ?? []}
            dimensionLabel={dimensionLabel}
            currency={cur}
          />
          <p className="caption">
            One file covers a short period, so each group is small. Check the number of
            matches before reading anything into the ROI.
          </p>
        </>
      )}
    </>
  )
}
