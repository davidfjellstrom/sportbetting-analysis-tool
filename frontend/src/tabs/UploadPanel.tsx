import { useState } from 'react'
import type { UploadChoice } from '../api/client'
import { currencyOptions, displayCurrency, type UploadState } from './uploadState'
import { Alert } from '../components/Alert'
import { CheckFailureBanner, CheckTable } from '../components/CheckReport'
import { Help } from '../components/Help'
import { Select } from '../components/Select'

// "A", "A or B", "A, B or C": the missing columns, read as a sentence.
function listed(items: string[]): string {
  return items.length < 2
    ? items.join('')
    : `${items.slice(0, -1).join(', ')} or ${items[items.length - 1]}`
}

/**
 * The top of the Explore tab: choose a file of your own, see whether it
 * passed the checks, and pick how its amounts are shown. The figures for it
 * are the explorer's, below.
 */
export function UploadPanel({
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
    if (state.file) onCheck(state.file, { unit: value, currency: displayCurrency(state.chosenCurrency) })
  }

  const result = state.status === 'done' || state.status === 'checking' ? state.result : undefined
  const fileCur = result?.file.currency_in_file ?? 'EUR'
  const fx = result?.file.fx

  return (
    <>
      <label className="uploader">
        <span className="label">Your own Sportmarket Pro export (CSV)</span>
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
      {state.file ? (
        <div className="uploader-actions">
          <button type="button" className="button-secondary" onClick={onRemove}>
            Remove file
          </button>
        </div>
      ) : (
        <p className="caption">
          Below is the full history. Upload your own export to explore that instead.
        </p>
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

      {result && (
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
            <Alert kind="info">
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
                  // The unit keeps its worth: 30 EUR becomes about 330 SEK.
                  if (state.file && v !== state.chosenCurrency) {
                    onCheck(state.file, {
                      unit: Number(state.unitText),
                      unitCurrency: displayCurrency(state.chosenCurrency),
                      currency: v,
                    })
                  }
                }}
                options={currencyOptions(result).map((c) => ({ value: c, label: c }))}
              />
            </label>
            <label className="control">
              <span className="label">
                Your unit ({state.chosenCurrency}){' '}
                <Help
                  text={`What one unit is worth to you, for example 10 or 100 ${state.chosenCurrency}. It starts at your typical stake in this file. What you set here is remembered for your next file.`}
                />
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

          {state.display === 'Currency' && fx && (
            <p className="caption">
              Converted from {fx.base} at 1 {fx.base} = {fx.rate} {fx.target}.
            </p>
          )}
        </>
      )}
    </>
  )
}
