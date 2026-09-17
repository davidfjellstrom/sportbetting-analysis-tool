// A dark navy theme, styled after a reference fintech dashboard rather than
// the data-viz reference palette the Streamlit app still uses. That palette's
// blue/red pair and eight categorical colours were measured for contrast and
// colour-blind separation against a specific warm-grey surface (#1a1a19);
// swapping to navy is a deliberate trade of that validation for the closer
// visual match. Nothing below has been re-measured — if that check matters
// again, re-run it against these hex values before relying on it.
export const PAGE = '#05070c'
export const SURFACE = '#10131f'
export const SURFACE_RAISED = '#161a2b'
export const GRID = '#242a3d'
export const BASELINE = '#2c3349'
export const INK = '#ffffff'
export const INK_MUTED = '#6d7690'
export const INK_SECONDARY = '#a9b2c7'
export const POSITIVE = '#3b82f6'
export const NEGATIVE = '#f4707f'

// The one accent in the app: title, focus rings, profit bars, the curve.
export const ACCENT = POSITIVE

// Categorical slots, in the fixed order the original palette prescribed —
// unvalidated on this surface, so treat the ordering as a style choice, not
// a safety guarantee, until someone checks it again. Eight is still the
// working ceiling.
export const SERIES_COLOURS = [
  '#3b82f6', // blue
  '#f2793a', // orange
  '#22b989', // aqua
  '#e2a100', // yellow
  '#ec6098', // magenta
  '#2fae4e', // green
  '#a594ff', // violet
  '#f4707f', // red
] as const
export const MAX_SERIES = SERIES_COLOURS.length

export const FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
