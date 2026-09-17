// The four Streamlit call-outs the app uses, as one component.
export function Alert({
  kind,
  icon,
  children,
}: {
  kind: 'info' | 'warning' | 'error'
  icon?: string
  children: React.ReactNode
}) {
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {icon && (
        <span className="alert-icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <div>{children}</div>
    </div>
  )
}
