export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  )
}

export function MetricRow({ children }: { children: React.ReactNode }) {
  return <div className="metric-row">{children}</div>
}
