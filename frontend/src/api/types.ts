// Mirrors api/schemas.py one to one. A field that exists there and not here
// is a bug in this file.

export type DimensionKey =
  | 'market_type'
  | 'selection'
  | 'bookie'
  | 'country'
  | 'competition'
  | 'market'
  | 'event_type'
  | 'stake_bucket'
  | 'n_bets_bucket'
  | 'year'
  | 'month'
  | 'weekday'

export type SortKey =
  | 'turnover_desc'
  | 'roi_desc'
  | 'roi_asc'
  | 'pl_desc'
  | 'fixtures_desc'
  | 'bets_per_fixture_desc'
  | 'name_asc'

export interface Check {
  name: string
  passed: boolean
  severity: 'ERROR' | 'WARN' | 'INFO'
  detail: string
}

export interface CheckReport {
  checks: Check[]
  ok: boolean
  n_errors: number
  n_warnings: number
}

export interface LoadReport {
  n_rows: number
  // null when an upload has no "Nr of Bets"; a row is not a bet.
  n_bets: number | null
  n_fixtures: number
  n_unmatched_rows: number
  unmatched_row_share: number
  turnover: number
  date_min: string | null
  date_max: string | null
  price_adjusted_coverage: number
}

export interface Totals {
  turnover: number
  pl: number
  bets: number | null
  fixtures: number
}

export interface PeriodPoint {
  period: string
  label: string
  tick: string
  turnover: number
  pl: number
  cumulative_pl: number
}

export interface PeriodSeries {
  bucket: 'day' | 'month'
  points: PeriodPoint[]
}

export interface SliceRow {
  slice: string
  bets: number | null
  fixtures: number
  bets_per_fixture: number | null
  turnover: number
  pl: number
  roi_pct: number
}

// ---- GET /api/overview ----

export interface OverviewResponse {
  currency: string
  matched: Totals
  fill_rate: number | null
  report: LoadReport
  checks: CheckReport
  cumulative: PeriodSeries
}

// ---- GET /api/explore/options ----

export interface LabelledKey {
  key: string
  label: string
}

// What a group needs for its own curve. null: that bar does not apply.
export interface CompareRules {
  min_turnover: number
  min_bets: number | null
  min_fixtures: number | null
  max_series: number
}

export interface ExploreOptions {
  currency: string
  date_min: string
  date_max: string
  // null when the data has no stake column; the stake filter is hidden.
  stake_ceiling: number | null
  // Empty when the data has no such column; the filter is hidden.
  market_types: string[]
  bookies: string[]
  dimensions: LabelledKey[]
  sorts: LabelledKey[]
  compare: CompareRules
}

// ---- GET /api/explore ----

export interface ExploreQuery {
  date_from: string
  date_to: string
  min_stake: number
  // Absent when the data has no stake column.
  max_stake?: number
  market_type?: string[]
  bookie?: string[]
  group_by: DimensionKey
  sort: SortKey
  min_fixtures: number
}

export interface ViewTotals {
  turnover: number
  pl: number
  roi_pct: number
  bets: number | null
}

export interface CurvePoint {
  month: string
  cum_pl: number
  cum_turnover: number
  cum_roi_pct: number
}

export interface ExploreOk {
  status: 'ok'
  currency: string
  view: ViewTotals
  groups_shown: number
  groups_total: number
  table: SliceRow[]
  bars_order: string[]
  eligible: string[]
  curves: Record<string, CurvePoint[]>
  // What one curve point covers; CurvePoint.month holds its start.
  curve_bucket: 'day' | 'month'
}

export interface ExploreStopped {
  status: 'stake_range_invalid' | 'empty'
  message: string
}

export type ExploreResponse = ExploreOk | ExploreStopped

// ---- POST /api/upload ----

// 1 base = rate target: the ECB reference rate of date.
export interface FxRate {
  base: string
  target: string
  rate: number
  date: string
}

export interface UploadFileInfo {
  name: string
  currency_in_file: string | null
  typical_stake: number | null
  unit_used: number
  // The rate the currency view was converted at; null in the file's own currency.
  fx: FxRate | null
}

export interface UploadView {
  currency: string
  matched: Totals
  cumulative: PeriodSeries
  // Keyed by the dimensions in UploadResponse.dimensions only.
  breakdown: Partial<Record<DimensionKey, SliceRow[]>>
  // The explorer's options for this file in this view's amounts; null when
  // no row matched and there is nothing to explore.
  explore_options: ExploreOptions | null
}

export interface UploadResponse {
  file: UploadFileInfo
  checks: CheckReport
  report: LoadReport
  // What this file can be grouped by; a subset when it left columns out.
  dimensions: LabelledKey[]
  // Export headers the file did not carry, e.g. ["Bookie"].
  missing_columns: string[]
  units: UploadView
  currency: UploadView
}
