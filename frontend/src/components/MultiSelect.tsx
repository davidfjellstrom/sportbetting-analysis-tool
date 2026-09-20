import { Help } from './Help'
import { Select } from './Select'

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
        <Select
          variant="inline"
          ariaLabel={`Add ${label.toLowerCase()}`}
          value=""
          onChange={(v) => onChange([...selected, v])}
          options={remaining.map((o) => ({ value: o, label: o }))}
          placeholder={full ? `Up to ${max}` : 'Choose an option'}
          disabled={full || remaining.length === 0}
        />
      </div>
    </div>
  )
}
