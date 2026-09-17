import { lazy, Suspense } from 'react'
import type { TopLevelSpec } from 'vega-lite'

const VegaChart = lazy(() => import('./VegaChart'))

/** Reserves the chart's height while Vega loads, so nothing below it jumps. */
export function LazyChart({ spec, height }: { spec: TopLevelSpec; height: number }) {
  return (
    <Suspense fallback={<div className="chart chart-loading" style={{ height }} />}>
      <VegaChart spec={spec} />
    </Suspense>
  )
}
