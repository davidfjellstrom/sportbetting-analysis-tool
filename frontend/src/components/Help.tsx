/** Streamlit's `help=` affordance: a small mark that explains on hover. */
export function Help({ text }: { text: string }) {
  return (
    <span className="help" title={text} aria-label={text} role="img">
      ?
    </span>
  )
}
