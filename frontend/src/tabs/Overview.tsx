import { useMemo } from 'react'
import type { OverviewResponse } from '../api/types'
import { cumulativeSpec } from '../charts/cumulative'
import { LazyChart } from '../components/LazyChart'
import { Metric, MetricRow } from '../components/Metric'
import { formatMonth, integer, money, percent } from '../format'

export function Overview({ data }: { data: OverviewResponse }) {
  const cur = data.currency
  const spec = useMemo(() => cumulativeSpec(data.cumulative, cur), [data, cur])
  return (
    <>
      <p className="intro">
        What you see here is one person's betting history: every bet placed
        through Sportmarket Pro from {formatMonth(data.report.date_min)} to{' '}
        {formatMonth(data.report.date_max)}, exactly as the platform exported it.
        Amounts are shown in units rather than money, so the pattern of the
        results is on display, not the sums.
        The Upload tab runs the same checks on an export of your own.
      </p>
      <MetricRow>
        <Metric label={`Matched turnover (${cur})`} value={money(data.matched.turnover, cur)} />
        <Metric label={`P/L (${cur})`} value={money(data.matched.pl, cur, 0, true)} />
        <Metric
          label="Fill rate"
          value={data.fill_rate === null ? 'nan%' : percent(data.fill_rate)}
        />
        <Metric label="Rows with odds info" value={percent(data.report.price_adjusted_coverage)} />
      </MetricRow>
      <MetricRow>
        <Metric label="Rows" value={integer(data.report.n_rows)} />
        <Metric label="Bets" value={integer(data.report.n_bets)} />
        <Metric label="Matches" value={integer(data.report.n_fixtures)} />
        <Metric label="Unmatched rows" value={integer(data.report.n_unmatched_rows)} />
      </MetricRow>

      <h3 className="accent">Cumulative P/L by month ({cur})</h3>
      <LazyChart spec={spec} height={320} />
    </>
  )
}
