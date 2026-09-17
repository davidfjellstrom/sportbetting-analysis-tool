import type { TopLevelSpec } from 'vega-lite'
import type { PeriodSeries } from '../api/types'
import { NEGATIVE, POSITIVE } from '../theme'
import { ZERO_RULE } from './config'
import { bucketLabels } from './cumulative'

/**
 * P/L per bucket, signed. What a short export actually has to show.
 *
 * The cumulative curve answers "where did this end up"; over a handful of
 * days that is one number and a slope. The bars answer "which days", which
 * is the only question a week of betting can actually settle.
 */
export function plBarsSpec(series: PeriodSeries, code: string): TopLevelSpec {
  const { label } = bucketLabels(series.bucket)
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 260,
    data: { values: series.points },
    layer: [
      {
        transform: [{ calculate: "datum.pl >= 0 ? 'Profit' : 'Loss'", as: 'direction' }],
        mark: { type: 'bar', cornerRadiusEnd: 3 },
        encoding: {
          // Ordinal, not temporal: on a time scale four daily bars are drawn
          // as four hairlines against a week of empty axis. A band scale
          // gives each bucket its share of the width. `sort: null` keeps the
          // series' own chronological order.
          x: {
            field: 'tick',
            type: 'nominal',
            title: null,
            sort: null,
            axis: { labelAngle: 0, labelLimit: 110 },
          },
          y: { field: 'pl', type: 'quantitative', title: `P/L (${code})` },
          color: {
            field: 'direction',
            type: 'nominal',
            scale: { domain: ['Profit', 'Loss'], range: [POSITIVE, NEGATIVE] },
            legend: { title: null, orient: 'top' },
          },
          tooltip: [
            { field: 'label', type: 'nominal', title: label },
            { field: 'pl', type: 'quantitative', title: `P/L (${code})`, format: '+,.0f' },
            {
              field: 'turnover',
              type: 'quantitative',
              title: `Turnover (${code})`,
              format: ',.0f',
            },
          ],
        },
      },
      ZERO_RULE,
    ],
  }
}
