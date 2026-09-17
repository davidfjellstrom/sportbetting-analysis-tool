import { describe, expect, it } from 'vitest'
import { compareSpec, measureLabel } from './compare'
import { roiBarsSpec } from './roiBars'

const row = (slice: string, pl: number) => ({
  slice,
  bets: 10,
  fixtures: 5,
  bets_per_fixture: 2,
  turnover: 100,
  pl,
  roi_pct: pl,
})

describe('roiBarsSpec', () => {
  it('keeps the API order and colours by the sign of P/L', () => {
    const spec = roiBarsSpec([row('a', 1), row('b', -1)], ['b', 'a'], 'Bookie', 'units') as {
      height: number
      layer: { encoding?: { x: { sort: string[] }; color: { scale: { range: string[] } }; tooltip: { title: string }[] } }[]
    }
    expect(spec.height).toBe(340)
    expect(spec.layer[0].encoding?.x.sort).toEqual(['b', 'a'])
    expect(spec.layer[0].encoding?.color.scale.range).toEqual(['#3987e5', '#e66767'])
    expect(spec.layer[0].encoding?.tooltip.map((t) => t.title)).toEqual([
      'Bookie', 'ROI %', 'Turnover (units)', 'P/L (units)', 'Matches', 'Bets',
    ])
  })
})

const curves = {
  a: [{ month: '2025-01-01', cum_pl: 1, cum_turnover: 10, cum_roi_pct: 10 }],
  b: [{ month: '2025-01-01', cum_pl: -1, cum_turnover: 10, cum_roi_pct: -10 }],
}

describe('compareSpec', () => {
  it('is a gradient area with no legend for one series', () => {
    const spec = compareSpec(curves, ['a'], 'cum_pl', 'Bookie', 'units') as {
      layer: { mark: { type: string }; encoding?: { color?: unknown } }[]
    }
    expect(spec.layer[0].mark.type).toBe('area')
    expect(spec.layer[0].encoding?.color).toBeUndefined()
    expect(spec.layer[1].mark.type).toBe('rule')
  })
  it('is lines in the picked order with palette slots in sequence', () => {
    const spec = compareSpec(curves, ['b', 'a'], 'cum_roi_pct', 'Bookie', 'units') as {
      layer: { mark: { type: string }; encoding?: { color: { scale: { domain: string[]; range: string[] } }; y: { title: string } } }[]
    }
    expect(spec.layer[0].mark.type).toBe('line')
    expect(spec.layer[0].encoding?.color.scale).toEqual({
      domain: ['b', 'a'],
      range: ['#3987e5', '#d95926'],
    })
    expect(spec.layer[0].encoding?.y.title).toBe('Cumulative ROI %')
  })
  it('refuses a ninth series', () => {
    const nine = Array.from({ length: 9 }, (_, i) => `s${i}`)
    expect(() => compareSpec({}, nine, 'cum_pl', 'x', 'units')).toThrow('at most 8')
  })
  it('names the measure', () => {
    expect(measureLabel('cum_pl', 'units')).toBe('Cumulative P/L (units)')
    expect(measureLabel('cum_roi_pct', 'units')).toBe('Cumulative ROI %')
  })
})
