import type { TopLevelSpec } from 'vega-lite'
import type { CurvePoint } from '../api/types'
import { ACCENT, MAX_SERIES, SERIES_COLOURS, SURFACE } from '../theme'
import { ZERO_RULE } from './config'

export type Measure = 'cum_pl' | 'cum_roi_pct'

export function measureLabel(measure: Measure, code: string): string {
  return measure === 'cum_pl' ? `Cumulative P/L (${code})` : 'Cumulative ROI %'
}

/**
 * The picked segments' monthly curves on one set of axes.
 *
 * One segment: the filled area reads best, and with a single series the
 * title names it — no legend needed. Several: lines, because stacked or
 * overlapping fills stop being readable the moment two segments cross. The
 * colour scale's domain is the picked order, so the first pick is always the
 * first palette slot; slots are assigned in sequence and never cycled.
 */
export function compareSpec(
  curves: Record<string, CurvePoint[]>,
  picked: string[],
  measure: Measure,
  dimensionLabel: string,
  code: string,
): TopLevelSpec {
  if (picked.length > MAX_SERIES) {
    throw new Error(`at most ${MAX_SERIES} series on one chart, got ${picked.length}`)
  }
  const values = picked.flatMap((slice) =>
    (curves[slice] ?? []).map((p) => ({ slice, ...p })),
  )
  const title = measureLabel(measure, code)
  const format = measure === 'cum_pl' ? '+,.0f' : '+.2f'
  const encoding = {
    x: { field: 'month', type: 'temporal' as const, title: null },
    y: { field: measure, type: 'quantitative' as const, title },
    tooltip: [
      { field: 'slice', type: 'nominal' as const, title: dimensionLabel },
      { field: 'month', type: 'temporal' as const, title: 'Month', format: '%b %Y' },
      { field: measure, type: 'quantitative' as const, title, format },
      {
        field: 'cum_turnover',
        type: 'quantitative' as const,
        title: `Turnover to date (${code})`,
        format: ',.0f',
      },
    ],
  }

  const series =
    picked.length === 1
      ? {
          mark: {
            type: 'area' as const,
            interpolate: 'monotone' as const,
            line: { color: ACCENT, strokeWidth: 2 },
            color: {
              gradient: 'linear' as const,
              stops: [
                { color: SURFACE, offset: 0 },
                { color: ACCENT, offset: 1 },
              ],
              x1: 1,
              x2: 1,
              y1: 1,
              y2: 0,
            },
          },
          encoding,
        }
      : {
          mark: { type: 'line' as const, interpolate: 'monotone' as const, strokeWidth: 2 },
          encoding: {
            ...encoding,
            color: {
              field: 'slice',
              type: 'nominal' as const,
              title: null,
              sort: picked,
              scale: { domain: picked, range: SERIES_COLOURS.slice(0, picked.length) },
              legend: { orient: 'top' as const },
            },
          },
        }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 380,
    data: { values, format: { parse: { month: "date:'%Y-%m-%d'" } } },
    layer: [series, ZERO_RULE],
  }
}
