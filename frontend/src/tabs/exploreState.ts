import type { DimensionKey, ExploreOptions, ExploreQuery, SortKey } from '../api/types'
import type { Measure } from '../charts/compare'

export interface ExploreState {
  dateFrom: string
  dateTo: string
  minStake: number
  maxStake: number
  marketTypes: string[]
  bookies: string[]
  groupBy: DimensionKey
  sort: SortKey
  minFixtures: number
  topN: number
  measure: Measure
  /** What is picked for the comparison, and the eligible list it was picked
   * against — a new eligible list resets the pick to the first three, as a
   * Streamlit multiselect does when its options change. */
  picked: string[]
  pickedFor: string
}

export function initialExploreState(options: ExploreOptions): ExploreState {
  return {
    dateFrom: options.date_min,
    dateTo: options.date_max,
    minStake: 0,
    maxStake: options.stake_ceiling,
    marketTypes: [],
    bookies: [],
    groupBy: 'market_type',
    sort: 'turnover_desc',
    minFixtures: 0,
    topN: 12,
    measure: 'cum_pl',
    picked: [],
    pickedFor: '',
  }
}

/** The part of the state that needs a new answer from the API. */
export function exploreQuery(state: ExploreState): ExploreQuery {
  return {
    date_from: state.dateFrom,
    date_to: state.dateTo,
    min_stake: state.minStake,
    max_stake: state.maxStake,
    market_type: state.marketTypes.length ? state.marketTypes : undefined,
    bookie: state.bookies.length ? state.bookies : undefined,
    group_by: state.groupBy,
    sort: state.sort,
    min_fixtures: state.minFixtures,
  }
}
