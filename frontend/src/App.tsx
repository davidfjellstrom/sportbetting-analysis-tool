import { useEffect, useState } from 'react'
import { ApiError, getOverview } from './api/client'
import type { OverviewResponse } from './api/types'
import { Alert } from './components/Alert'
import { HistoryChecks } from './components/CheckReport'
import { Tabs } from './components/Tabs'
import { Overview } from './tabs/Overview'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'upload', label: 'Upload' },
  { key: 'explore', label: 'Explore' },
]

type Loaded =
  | { state: 'loading' }
  | { state: 'no-data'; message: string }
  | { state: 'error'; message: string }
  | { state: 'ready'; overview: OverviewResponse }

export default function App() {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' })
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    getOverview()
      .then((overview) => setLoaded({ state: 'ready', overview }))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 503) {
          setLoaded({ state: 'no-data', message: error.message })
        } else {
          setLoaded({ state: 'error', message: String(error) })
        }
      })
  }, [])

  return (
    <main className="page">
      <h1 className="accent">Sportmarket analysis</h1>

      {loaded.state === 'loading' && <div className="loading">Loading…</div>}
      {loaded.state === 'no-data' && (
        <Alert kind="warning" icon="📄">
          {loaded.message}
        </Alert>
      )}
      {loaded.state === 'error' && (
        <Alert kind="error" icon="🚨">
          Could not reach the API: {loaded.message}
        </Alert>
      )}

      {loaded.state === 'ready' && (
        <>
          {/* A failed check is a banner above every tab: no figure below it
              can be trusted. Green checks are silent. */}
          <HistoryChecks report={loaded.overview.checks} />
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
          <section className="tab-panel" role="tabpanel">
            {tab === 'overview' && <Overview data={loaded.overview} />}
            {tab === 'upload' && <Alert kind="info">Not built yet.</Alert>}
            {tab === 'explore' && <Alert kind="info">Not built yet.</Alert>}
          </section>
        </>
      )}
    </main>
  )
}
