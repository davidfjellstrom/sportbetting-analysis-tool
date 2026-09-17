import { describe, expect, it } from 'vitest'
import type { PeriodPoint } from '../api/types'
import { bucketLabels, cumulativeSpec, curveRules } from './cumulative'

function points(cumulative: number[]): PeriodPoint[] {
  return cumulative.map((c, i) => ({
    period: `2025-01-${String(i + 1).padStart(2, '0')}`,
    label: `${i + 1} Jan 2025`,
    tick: `${i + 1} Jan`,
    turnover: 1,
    pl: i === 0 ? c : c - cumulative[i - 1],
    cumulative_pl: c,
  }))
}

describe('curveRules', () => {
  it('interpolates monotone only above twelve buckets', () => {
    expect(curveRules(points(Array(12).fill(1))).interpolate).toBe('linear')
    expect(curveRules(points(Array(13).fill(1))).interpolate).toBe('monotone')
  })
  it('draws points only up to forty buckets', () => {
    expect(curveRules(points(Array(40).fill(1))).drawPoints).toBe(true)
    expect(curveRules(points(Array(41).fill(1))).drawPoints).toBe(false)
  })
  it('flags a curve that ever dips below zero', () => {
    expect(curveRules(points([1, 2, 0])).everNegative).toBe(false)
    expect(curveRules(points([1, -0.5, 2])).everNegative).toBe(true)
  })
})

describe('cumulativeSpec', () => {
  it('is a gradient area with no zero rule when never negative', () => {
    const spec = cumulativeSpec({ bucket: 'month', points: points([1, 2]) }, 'units')
    const layers = (spec as { layer: unknown[] }).layer
    expect(layers).toHaveLength(1)
    const mark = (layers[0] as { mark: { type: string; color: unknown } }).mark
    expect(mark.type).toBe('area')
    expect(mark.color).toMatchObject({ gradient: 'linear' })
  })
  it('is a plain line plus a zero rule when ever negative', () => {
    const spec = cumulativeSpec({ bucket: 'month', points: points([1, -1]) }, 'units')
    const layers = (spec as { layer: unknown[] }).layer
    expect(layers).toHaveLength(2)
    expect((layers[0] as { mark: { type: string } }).mark.type).toBe('line')
    expect((layers[1] as { mark: { type: string } }).mark.type).toBe('rule')
  })
  it('ticks daily and formats by bucket', () => {
    expect(bucketLabels('day')).toEqual({ tickFormat: '%d %b', label: 'Day' })
    expect(bucketLabels('month')).toEqual({ tickFormat: '%b %Y', label: 'Month' })
    const spec = cumulativeSpec({ bucket: 'day', points: points([1]) }, 'EUR')
    const axis = (spec as { layer: { encoding: { x: { axis: unknown } } }[] })
      .layer[0].encoding.x.axis
    expect(axis).toEqual({ format: '%d %b', tickCount: { interval: 'day', step: 1 } })
  })
  it('names the currency on the axis and in the tooltip', () => {
    const spec = cumulativeSpec({ bucket: 'month', points: points([1]) }, 'units')
    const encoding = (spec as { layer: { encoding: { y: { title: string }; tooltip: { title: string }[] } }[] })
      .layer[0].encoding
    expect(encoding.y.title).toBe('Cumulative P/L (units)')
    expect(encoding.tooltip.map((t) => t.title)).toEqual([
      'Month', 'Cumulative (units)', 'That month (units)', 'Turnover (units)',
    ])
  })
})
