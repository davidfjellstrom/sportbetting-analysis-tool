import { useEffect, useRef } from 'react'
import embed, { type Result } from 'vega-embed'
import type { TopLevelSpec } from 'vega-lite'
import { CHART_CONFIG } from '../charts/config'

// The one place Vega is imported. App.tsx loads this component lazily so the
// metrics and tables paint before the (large) chart runtime arrives.
export default function VegaChart({ spec }: { spec: TopLevelSpec }) {
  const host = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let result: Result | undefined
    let cancelled = false
    if (host.current) {
      embed(host.current, spec, {
        actions: false,
        renderer: 'svg',
        config: CHART_CONFIG,
        tooltip: { theme: 'dark' },
      }).then((r) => {
        if (cancelled) r.finalize()
        else result = r
      })
    }
    return () => {
      cancelled = true
      result?.finalize()
    }
  }, [spec])

  return <div className="chart" ref={host} />
}
