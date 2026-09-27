import type { DimensionKey, ExploreOptions, ExploreQuery, SortKey } from '../api/types'
import type { Measure } from '../charts/compare'

export interface ExploreState {
  dateFrom: string
  dateTo: string
  minStake: number
  /** null when the data has no stake column to filter on. */
  maxStake: number | null
  marketTypes: string[]
  bookies: string[]
  groupBy: DimensionKey
  /** Split each group by selection too, where the grouping allows it. */
  splitBySelection: boolean
  sort: SortKey
  minFixtures: number
  topN: number
  measure: Measure
  /** What is picked for the comparison, and the eligible list it was picked
   * against — a new eligible list resets the pick to the first three. */
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
    // An upload may have no market type; start on something it does have.
    groupBy: options.dimensions.some((d) => d.key === 'market_type')
      ? 'market_type'
      : (options.dimensions[0].key as DimensionKey),
    splitBySelection: false,
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
    max_stake: state.maxStake ?? undefined,
    market_type: state.marketTypes.length ? state.marketTypes : undefined,
    bookie: state.bookies.length ? state.bookies : undefined,
    group_by: state.groupBy,
    sort: state.sort,
    min_fixtures: state.minFixtures,
    split_by_selection: state.splitBySelection || undefined,
  }
}
