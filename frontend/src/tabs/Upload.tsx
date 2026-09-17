import { useMemo, useState } from 'react'
import { ApiError, postUpload } from '../api/client'
import type { DimensionKey, LabelledKey, UploadResponse } from '../api/types'
import type { UploadState } from './uploadState'
import { cumulativeSpec } from '../charts/cumulative'
import { plBarsSpec } from '../charts/plBars'
import { Alert } from '../components/Alert'
import { CheckFailureBanner, CheckTable } from '../components/CheckReport'
import { Help } from '../components/Help'
import { LazyChart } from '../components/LazyChart'
import { Metric, MetricRow } from '../components/Metric'
import { SliceTable } from '../components/SliceTable'
import { integer, money, percent } from '../format'

// Currencies an uploader can label their file with. A file whose currency
// column names something else gets that added at the front of the list.
const DISPLAY_CURRENCIES = ['EUR', 'USD', 'SEK']

// Vercel rejects a request body above this before the API sees it; saying so
// here is clearer than a bare 413.
const MAX_UPLOAD_BYTES = 4.5 * 1024 * 1024

function currencyOptions(result: UploadResponse): string[] {
  const fileCur = result.file.currency_in_file
  const options = DISPLAY_CURRENCIES.filter((c) => c !== fileCur)
  if (fileCur) options.unshift(fileCur)
  return options
}

function defaultUnitText(result: UploadResponse): string {
  return result.file.typical_stake === null ? '1.00' : result.file.typical_stake.toFixed(2)
}

export function Upload({
  state,
  setState,
  dimensions,
}: {
  state: UploadState
  setState: (update: (s: UploadState) => UploadState) => void
  dimensions: LabelledKey[]
}) {
  const [unitDraft, setUnitDraft] = useState<string | null>(null)

  function check(file: File, unit?: number) {
    if (file.size > MAX_UPLOAD_BYTES) {
      setState((s) => ({
        ...s,
        file,
        status: 'error',
        result: undefined,
        error: `${file.name} is ${(file.size / 1024 / 1024).toFixed(2)} MB; files above 4.5 MB cannot be checked.`,
      }))
      return
    }
    setState((s) => ({ ...s, file, status: 'checking', error: undefined }))
    postUpload(file, unit)
      .then((result) =>
        setState((s) => ({
          ...s,
          status: 'done',
          result,
          // A fresh file resets the viewer's choices; a new unit keeps them.
          chosenCurrency: unit === undefined ? currencyOptions(result)[0] : s.chosenCurrency,
          unitText: unit === undefined ? defaultUnitText(result) : unit.toFixed(2),
        })),
      )
      .catch((error: unknown) =>
        setState((s) => ({
          ...s,
          status: 'error',
          result: undefined,
          error: error instanceof ApiError ? error.message : String(error),
        })),
      )
  }

  function commitUnit() {
    if (unitDraft === null) return
    const value = Number(unitDraft)
    setUnitDraft(null)
    if (!Number.isFinite(value) || value < 0.01) return
    if (value.toFixed(2) === state.unitText) return
    if (state.file) check(state.file, value)
  }

  const result = state.status === 'done' || state.status === 'checking' ? state.result : undefined
  const cur = state.display === 'Units' ? 'units' : state.chosenCurrency
  const view = result ? (state.display === 'Units' ? result.units : result.currency) : undefined
  const cumulative = useMemo(
    () => (view ? cumulativeSpec(view.cumulative, cur) : null),
    [view, cur],
  )
  const bars = useMemo(() => (view ? plBarsSpec(view.cumulative, cur) : null), [view, cur])
  const dimensionLabel =
    dimensions.find((d) => d.key === state.groupBy)?.label ?? state.groupBy

  return (
    <>
      <h3 className="accent">Check a new export</h3>
      <p className="caption">
        Upload your own Sportmarket Pro export to see how it went. The file is
        checked, shown on its own and never added to the main dataset. One file
        shows what happened — it cannot tell you what works.
      </p>

      <label className="uploader">
        <span className="label">Sportmarket Pro export (CSV)</span>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) check(file)
          }}
        />
        <span className="uploader-hint">
          {state.file ? state.file.name : 'Drag and drop or browse · CSV'}
        </span>
      </label>

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
      {state.status === 'checking' && !result && <div className="loading">Checking…</div>}

      {result && view && cumulative && bars && (
        <>
          {result.checks.ok ? (
            <details className="expander" key={`${result.file.name}:${result.report.n_rows}`}>
              <summary>
                {result.checks.checks.length} integrity checks passed
                {result.checks.n_warnings ? `, ${result.checks.n_warnings} warning(s)` : ''}
              </summary>
              <CheckTable report={result.checks} />
              <p className="caption">Problems are reported, never fixed automatically.</p>
            </details>
          ) : (
            <>
              <CheckFailureBanner report={result.checks} />
              <CheckTable report={result.checks} />
            </>
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
                <Help text="The currency your file is in. Taken from the file when it says so. Nothing is converted." />
              </span>
              <select
                value={state.chosenCurrency}
                onChange={(e) => setState((s) => ({ ...s, chosenCurrency: e.target.value }))}
              >
                {currencyOptions(result).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="control">
              <span className="label">
                1 unit = ({state.chosenCurrency}){' '}
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
            <Metric label="Bets" value={integer(result.report.n_bets)} />
            <Metric label="Matches" value={integer(result.report.n_fixtures)} />
          </MetricRow>
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
            <select
              value={state.groupBy}
              onChange={(e) =>
                setState((s) => ({ ...s, groupBy: e.target.value as DimensionKey }))
              }
            >
              {dimensions.map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
          <SliceTable
            rows={view.breakdown[state.groupBy]}
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
