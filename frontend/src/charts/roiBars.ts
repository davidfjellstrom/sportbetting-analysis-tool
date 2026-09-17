import type { TopLevelSpec } from 'vega-lite'
import type { SliceRow } from '../api/types'
import { NEGATIVE, POSITIVE } from '../theme'
import { ZERO_RULE } from './config'

/** ROI per slice for the largest slices, in the order the API ranked them. */
export function roiBarsSpec(
  rows: SliceRow[],
  order: string[],
  dimensionLabel: string,
  code: string,
): TopLevelSpec {
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 340,
    data: { values: rows },
    layer: [
      {
        transform: [{ calculate: "datum.pl >= 0 ? 'Profit' : 'Loss'", as: 'direction' }],
        mark: { type: 'bar', cornerRadiusEnd: 4 },
        encoding: {
          x: {
            field: 'slice',
            type: 'nominal',
            sort: order,
            title: null,
            axis: { labelAngle: -40, labelLimit: 150 },
          },
          y: {
            field: 'roi_pct',
            type: 'quantitative',
            title: 'ROI % (turnover-weighted)',
          },
          color: {
            field: 'direction',
            type: 'nominal',
            scale: { domain: ['Profit', 'Loss'], range: [POSITIVE, NEGATIVE] },
            legend: { title: null, orient: 'top' },
          },
          tooltip: [
            { field: 'slice', type: 'nominal', title: dimensionLabel },
            { field: 'roi_pct', type: 'quantitative', title: 'ROI %', format: '+.2f' },
            {
              field: 'turnover',
              type: 'quantitative',
              title: `Turnover (${code})`,
              format: ',.0f',
            },
            { field: 'pl', type: 'quantitative', title: `P/L (${code})`, format: '+,.0f' },
            { field: 'fixtures', type: 'quantitative', title: 'Matches', format: ',' },
            { field: 'bets', type: 'quantitative', title: 'Bets', format: ',' },
          ],
        },
      },
      ZERO_RULE,
    ],
  }
}
