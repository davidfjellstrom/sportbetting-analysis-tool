// Number formatting that matches the Python app character for character.
// Formatting is a display concern; every number arrives computed from the API.

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: '€',
  GBP: '£',
  USD: '$',
  SEK: 'kr',
}
// Written after the number ("218 kr"), not before it.
const SUFFIX_CURRENCIES = new Set(['SEK'])

/**
 * Python's `f"{value:,.{decimals}f}"`, including its rounding: half to even,
 * so 2.5 prints as 2 on both sides and the two apps never disagree by one.
 */
export function fixed(value: number, decimals = 0): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    roundingMode: 'halfEven',
  } as Intl.NumberFormatOptions)
}

/** Python's `f"{value:+,.{decimals}f}"`: an explicit sign, zero counts as plus. */
export function signed(value: number, decimals = 0): string {
  const sign = value < 0 ? '-' : '+'
  return sign + fixed(Math.abs(value), decimals)
}

/** Python's `f"{value:,}"` on an integer. */
export function integer(value: number): string {
  return fixed(value, 0)
}

/** Python's `f"{value:.{decimals}%}"`. */
export function percent(value: number, decimals = 1): string {
  return (100 * value).toFixed(decimals) + '%'
}

/**
 * Format an amount so the currency is never in doubt.
 *
 * `signed` on P/L: a bare "1,204" reads as a number, "+€1,204" reads as a
 * result. Filters can push any slice negative, so the sign carries meaning.
 */
export function money(
  value: number,
  code: string,
  decimals = 0,
  withSign = false,
): string {
  const sign = withSign ? (value < 0 ? '-' : '+') : ''
  const magnitude = withSign ? Math.abs(value) : value
  const number = fixed(magnitude, decimals)
  const symbol = CURRENCY_SYMBOLS[code]
  if (symbol && SUFFIX_CURRENCIES.has(code)) return `${sign}${number} ${symbol}`
  if (symbol) return `${sign}${symbol}${number}`
  if (code === 'units') return `${sign}${number} u`
  return `${sign}${number} ${code}`
}
