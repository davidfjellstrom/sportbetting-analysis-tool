import { describe, expect, it } from 'vitest'
import { plBarsSpec } from './plBars'

const series = {
  bucket: 'day' as const,
  points: [
    { period: '2025-03-01', label: '01 Mar 2025', tick: '01 Mar', turnover: 10, pl: 2, cumulative_pl: 2 },
    { period: '2025-03-02', label: '02 Mar 2025', tick: '02 Mar', turnover: 10, pl: -3, cumulative_pl: -1 },
  ],
}

describe('plBarsSpec', () => {
  it('is signed bars on an ordinal axis with a zero rule', () => {
    const spec = plBarsSpec(series, 'EUR') as {
      height: number
      layer: { mark: { type: string }; encoding?: { x: { sort: unknown; type: string }; color: { scale: unknown } } }[]
    }
    expect(spec.height).toBe(260)
    expect(spec.layer).toHaveLength(2)
    expect(spec.layer[0].mark.type).toBe('bar')
    expect(spec.layer[0].encoding?.x.type).toBe('nominal')
    expect(spec.layer[0].encoding?.x.sort).toBeNull()
    expect(spec.layer[0].encoding?.color.scale).toEqual({
      domain: ['Profit', 'Loss'],
      range: ['#3987e5', '#e66767'],
    })
    expect(spec.layer[1].mark.type).toBe('rule')
  })
  it('titles by bucket and currency', () => {
    const spec = plBarsSpec(series, 'EUR') as {
      layer: { encoding?: { y: { title: string }; tooltip: { title: string }[] } }[]
    }
    expect(spec.layer[0].encoding?.y.title).toBe('P/L (EUR)')
    expect(spec.layer[0].encoding?.tooltip.map((t) => t.title)).toEqual([
      'Day', 'P/L (EUR)', 'Turnover (EUR)',
    ])
  })
})
