import { Help } from './Help'

/** Streamlit's multiselect: chips for what is picked, a list for the rest. */
export function MultiSelect({
  label,
  options,
  selected,
  onChange,
  max,
  help,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
  max?: number
  help?: string
}) {
  const remaining = options.filter((o) => !selected.includes(o))
  const full = max !== undefined && selected.length >= max
  return (
    <div className="control multiselect">
      <span className="label">
        {label} {help && <Help text={help} />}
      </span>
      <div className="chips">
        {selected.map((s) => (
          <span key={s} className="chip">
            {s}
            <button
              type="button"
              aria-label={`Remove ${s}`}
              onClick={() => onChange(selected.filter((x) => x !== s))}
            >
              ×
            </button>
          </span>
        ))}
        <select
          aria-label={`Add ${label.toLowerCase()}`}
          value=""
          disabled={full || remaining.length === 0}
          onChange={(e) => {
            if (e.target.value) onChange([...selected, e.target.value])
          }}
        >
          <option value="">{full ? `Up to ${max}` : 'Choose an option'}</option>
          {remaining.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
