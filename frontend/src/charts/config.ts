import type { Config } from 'vega-lite'
import {
  BASELINE,
  FONT,
  GRID,
  INK_MUTED,
  INK_SECONDARY,
  SURFACE,
} from '../theme'

// Recessive grid and axes, ink in text tokens rather than series colour.
export const CHART_CONFIG: Config = {
  background: 'transparent',
  font: FONT,
  view: { stroke: null, fill: SURFACE },
  axis: {
    grid: true,
    gridColor: GRID,
    gridWidth: 1,
    domainColor: BASELINE,
    tickColor: BASELINE,
    labelColor: INK_MUTED,
    titleColor: INK_SECONDARY,
    labelFontSize: 11,
    titleFontSize: 12,
    titleFontWeight: 'normal',
  },
  legend: {
    labelColor: INK_SECONDARY,
    titleColor: INK_SECONDARY,
    labelFontSize: 12,
    symbolType: 'square',
    symbolSize: 140,
  },
}

/** A tooltip format for an amount: two decimals in units, whole in currency. */
export function amountFormat(code: string, withSign = false): string {
  return (withSign ? '+' : '') + (code === 'units' ? ',.2f' : ',.0f')
}

/** A horizontal rule at zero, drawn in the baseline colour. */
export const ZERO_RULE = {
  data: { values: [{ y: 0 }] },
  mark: { type: 'rule' as const, color: BASELINE, strokeWidth: 1 },
  encoding: { y: { field: 'y', type: 'quantitative' as const } },
}
