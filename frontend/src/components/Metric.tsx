import { Children } from 'react'

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  )
}

/** As many equal columns as there are metrics, like `st.columns(n)`. */
export function MetricRow({ children }: { children: React.ReactNode }) {
  const n = Children.count(children)
  return (
    <div className="metric-row" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
      {children}
    </div>
  )
}
