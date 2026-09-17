import { useCallback, useEffect, useState } from 'react'
import { ApiError, getExploreOptions, getOverview } from './api/client'
import type { ExploreOptions, OverviewResponse } from './api/types'
import { Alert } from './components/Alert'
import { HistoryChecks } from './components/CheckReport'
import { Tabs } from './components/Tabs'
import { Overview } from './tabs/Overview'
import { Explore } from './tabs/Explore'
import { initialExploreState, type ExploreState } from './tabs/exploreState'
import { Upload } from './tabs/Upload'
import { INITIAL_UPLOAD_STATE, type UploadState } from './tabs/uploadState'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'upload', label: 'Upload' },
  { key: 'explore', label: 'Explore' },
]

type Loaded =
  | { state: 'loading' }
  | { state: 'no-data'; message: string }
  | { state: 'error'; message: string }
  | { state: 'ready'; overview: OverviewResponse; options: ExploreOptions }

export default function App() {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' })
  const [tab, setTab] = useState('overview')
  // Held here rather than in the tab, so a checked file survives a visit to
  // another tab — as it does in the Streamlit app, where every tab is live.
  const [upload, setUpload] = useState<UploadState>(INITIAL_UPLOAD_STATE)
  const [explore, setExplore] = useState<ExploreState | null>(null)
  const updateExplore = useCallback(
    (update: (s: ExploreState) => ExploreState) =>
      setExplore((s) => (s === null ? s : update(s))),
    [],
  )

  useEffect(() => {
    Promise.all([getOverview(), getExploreOptions()])
      .then(([overview, options]) => {
        setExplore(initialExploreState(options))
        setLoaded({ state: 'ready', overview, options })
      })
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
      <h1 className="accent title">
        Sportmarket analysis <span className="badge">Beta</span>
      </h1>

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
            {tab === 'upload' && (
              <Upload
                state={upload}
                setState={setUpload}
                dimensions={loaded.options.dimensions}
              />
            )}
            {tab === 'explore' && explore && (
              <Explore state={explore} setState={updateExplore} options={loaded.options} />
            )}
          </section>
        </>
      )}
    </main>
  )
}
