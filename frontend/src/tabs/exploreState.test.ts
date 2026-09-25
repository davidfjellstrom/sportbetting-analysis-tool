import { describe, expect, it } from 'vitest'
import type { ExploreOptions } from '../api/types'
import { exploreQuery, initialExploreState } from './exploreState'

const options: ExploreOptions = {
  currency: 'units',
  date_min: '2026-09-01',
  date_max: '2026-09-25',
  stake_ceiling: 30,
  market_types: ['ah', 'ou'],
  bookies: ['pinnacle'],
  dimensions: [
    { key: 'market_type', label: 'Market type' },
    { key: 'year', label: 'Year' },
  ],
  sorts: [{ key: 'turnover_desc', label: 'Turnover (largest first)' }],
  compare: { min_turnover: 28, min_bets: null, min_fixtures: 20, max_series: 8 },
}

describe('initialExploreState', () => {
  it('starts on market type and the full stake range when the data has them', () => {
    const state = initialExploreState(options)
    expect(state.groupBy).toBe('market_type')
    expect(exploreQuery(state).max_stake).toBe(30)
  })

  it('falls back to what an upload has', () => {
    const state = initialExploreState({
      ...options,
      stake_ceiling: null,
      dimensions: [{ key: 'year', label: 'Year' }],
    })
    expect(state.groupBy).toBe('year')
    expect(exploreQuery(state).max_stake).toBeUndefined()
  })
})
