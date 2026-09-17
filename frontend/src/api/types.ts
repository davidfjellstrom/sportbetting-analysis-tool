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
  n_bets: number
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
  bets: number
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
  bets: number
  fixtures: number
  bets_per_fixture: number
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

export interface CompareRules {
  min_turnover: number
  min_bets: number
  max_series: number
}

export interface ExploreOptions {
  currency: string
  date_min: string
  date_max: string
  stake_ceiling: number
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
  max_stake: number
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
  bets: number
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
}

export interface ExploreStopped {
  status: 'stake_range_invalid' | 'empty'
  message: string
}

export type ExploreResponse = ExploreOk | ExploreStopped

// ---- POST /api/upload ----

export interface UploadFileInfo {
  name: string
  currency_in_file: string | null
  typical_stake: number | null
  unit_used: number
}

export interface UploadView {
  currency: string
  matched: Totals
  cumulative: PeriodSeries
  breakdown: Record<DimensionKey, SliceRow[]>
}

export interface UploadResponse {
  file: UploadFileInfo
  checks: CheckReport
  report: LoadReport
  units: UploadView
  currency: UploadView
}
