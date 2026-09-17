import type { TopLevelSpec } from 'vega-lite'
import type { PeriodPoint, PeriodSeries } from '../api/types'
import { POSITIVE, SURFACE } from '../theme'
import { ZERO_RULE } from './config'

/** Cumulative P/L over time — a lifetime by month, one export by day. */
export interface CurveRules {
  /** Straight segments below a dozen buckets: monotone smoothing between four
   * daily points invents a shape the data has nothing to say about. */
  interpolate: 'monotone' | 'linear'
  /** An area anchored at zero fills between the curve and the baseline, and
   * the gradient runs one way only. On a curve that dips below zero the fill
   * lands *above* the line and a losing week reads as a solid block of
   * profit-blue. Where that can happen, drop to a line. */
  everNegative: boolean
  /** Buckets stay drawn when there are few of them: over a week the curve is
   * four or five points and the line alone hides how little is behind it. */
  drawPoints: boolean
}

export function curveRules(points: PeriodPoint[]): CurveRules {
  return {
    interpolate: points.length > 12 ? 'monotone' : 'linear',
    everNegative: points.some((p) => p.cumulative_pl < 0),
    drawPoints: points.length <= 40,
  }
}

/** Axis tick format and the word for one bucket, by resolution. */
export function bucketLabels(bucket: PeriodSeries['bucket']) {
  return bucket === 'day'
    ? { tickFormat: '%d %b', label: 'Day' }
    : { tickFormat: '%b %Y', label: 'Month' }
}

export function cumulativeSpec(series: PeriodSeries, code: string): TopLevelSpec {
  const rules = curveRules(series.points)
  const { tickFormat, label } = bucketLabels(series.bucket)
  const point = rules.drawPoints ? { color: POSITIVE, size: 55 } : false

  const mark = rules.everNegative
    ? {
        type: 'line' as const,
        interpolate: rules.interpolate,
        strokeWidth: 2,
        color: POSITIVE,
        point,
      }
    : {
        type: 'area' as const,
        interpolate: rules.interpolate,
        line: { color: POSITIVE, strokeWidth: 2 },
        point,
        color: {
          gradient: 'linear' as const,
          stops: [
            { color: SURFACE, offset: 0 },
            { color: POSITIVE, offset: 1 },
          ],
          x1: 1,
          x2: 1,
          y1: 1,
          y2: 0,
        },
      }

  const curve = {
    mark,
    encoding: {
      x: {
        field: 'period',
        type: 'temporal' as const,
        title: null,
        axis: {
          format: tickFormat,
          // Left to itself Vega ticks a four-day domain every twelve hours
          // and, formatted as a date, prints each day twice.
          ...(series.bucket === 'day'
            ? { tickCount: { interval: 'day' as const, step: 1 } }
            : {}),
        },
      },
      y: {
        field: 'cumulative_pl',
        type: 'quantitative' as const,
        title: `Cumulative P/L (${code})`,
      },
      tooltip: [
        { field: 'label', type: 'nominal' as const, title: label },
        {
          field: 'cumulative_pl',
          type: 'quantitative' as const,
          title: `Cumulative (${code})`,
          format: ',.0f',
        },
        {
          field: 'pl',
          type: 'quantitative' as const,
          title: `That ${label.toLowerCase()} (${code})`,
          format: '+,.0f',
        },
        {
          field: 'turnover',
          type: 'quantitative' as const,
          title: `Turnover (${code})`,
          format: ',.0f',
        },
      ],
    },
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 320,
    data: {
      values: series.points,
      // Parsed as local dates: a bare ISO string would be read as UTC and
      // could land on the previous day west of Greenwich.
      format: { parse: { period: "date:'%Y-%m-%d'" } },
    },
    layer: rules.everNegative ? [curve, ZERO_RULE] : [curve],
  }
}
