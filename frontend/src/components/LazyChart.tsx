import { lazy, Suspense } from 'react'
import type { TopLevelSpec } from 'vega-lite'

const VegaChart = lazy(() => import('./VegaChart'))

/**
 * Reserves the chart's height while Vega loads, so nothing below it jumps.
 *
 * The card chrome (background, border, padding) lives on this wrapper, not
 * on the div Vega measures for its "container" width — padding on that div
 * would shrink the space available after Vega has already sized to it,
 * pushing the chart past its own right edge.
 */
export function LazyChart({ spec, height }: { spec: TopLevelSpec; height: number }) {
  return (
    <div className="chart-card">
      <Suspense fallback={<div className="chart-loading" style={{ height }} />}>
        <VegaChart spec={spec} />
      </Suspense>
    </div>
  )
}
