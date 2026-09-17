import { useState } from 'react'
import { Help } from './Help'

/**
 * Streamlit's number_input: the value is committed on Enter or when the
 * field loses focus, not on every keystroke, so a request is not fired for
 * each digit typed.
 */
export function NumberField({
  label,
  value,
  onCommit,
  min,
  step,
  help,
  disabled,
}: {
  label: string
  value: number
  onCommit: (value: number) => void
  min?: number
  step?: number
  help?: string
  disabled?: boolean
}) {
  const [draft, setDraft] = useState<string | null>(null)

  function commit() {
    if (draft === null) return
    const parsed = Number(draft)
    setDraft(null)
    if (!Number.isFinite(parsed)) return
    const clamped = min !== undefined && parsed < min ? min : parsed
    if (clamped !== value) onCommit(clamped)
  }

  return (
    <label className="control">
      <span className="label">
        {label} {help && <Help text={help} />}
      </span>
      <input
        type="number"
        min={min}
        step={step}
        disabled={disabled}
        value={draft ?? String(value)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        }}
      />
    </label>
  )
}
