// Chart ink, from the data-viz reference palette (dark instance) — the same
// hex values as app/streamlit_app.py and .streamlit/config.toml. The diverging
// pair is blue<->red, not red<->green: red/green is the conventional
// profit/loss pairing and the one that collapses under the commonest colour
// blindness.
export const PAGE = '#0d0d0d'
export const SURFACE = '#1a1a19'
export const GRID = '#2c2c2a'
export const BASELINE = '#383835'
export const INK = '#ffffff'
export const INK_MUTED = '#898781'
export const INK_SECONDARY = '#c3c2b7'
export const POSITIVE = '#3987e5'
export const NEGATIVE = '#e66767'

// The one accent in the app: title, active tab, profit bars, the curve.
export const ACCENT = POSITIVE

// Categorical slots, in the fixed order the palette prescribes — the ordering
// is the colour-blindness safety mechanism, so slots are assigned in sequence
// and never cycled. Eight is the hard ceiling.
export const SERIES_COLOURS = [
  '#3987e5', // blue
  '#d95926', // orange
  '#199e70', // aqua
  '#c98500', // yellow
  '#d55181', // magenta
  '#008300', // green
  '#9085e9', // violet
  '#e66767', // red
] as const
export const MAX_SERIES = SERIES_COLOURS.length

export const FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
