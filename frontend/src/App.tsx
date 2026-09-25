import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  getExplore,
  getExploreOptions,
  getOverview,
  postExploreUpload,
  type UploadChoice,
} from './api/client'
import type { ExploreOptions, ExploreQuery, OverviewResponse } from './api/types'
import { Alert } from './components/Alert'
import { HistoryChecks } from './components/CheckReport'
import { Tabs } from './components/Tabs'
import { Overview } from './tabs/Overview'
import { Explore } from './tabs/Explore'
import { initialExploreState, type ExploreState } from './tabs/exploreState'
import { Upload } from './tabs/Upload'
import { INITIAL_UPLOAD_STATE, checkUpload, type UploadState } from './tabs/uploadState'
import { clearUpload, loadUpload, saveUpload } from './uploadStore'

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

  // ---- the uploaded file --------------------------------------------------
  // Once a file is in, Explore works on that file alone; Overview keeps the
  // history. The file is kept in this browser (uploadStore) so a reload
  // restores it; the server never keeps it.

  const onCheck = useCallback((file: File, choice: UploadChoice = {}) => {
    void checkUpload(file, choice, setUpload).then((accepted) => {
      if (accepted) void saveUpload({ file, savedAt: Date.now(), ...choice })
    })
  }, [])

  const onRemove = useCallback(() => {
    setUpload(INITIAL_UPLOAD_STATE)
    void clearUpload()
  }, [])

  useEffect(() => {
    void loadUpload().then((stored) => {
      if (stored) onCheck(stored.file, { unit: stored.unit, currency: stored.currency })
    })
  }, [onCheck])

  const uploaded = upload.status === 'done' ? upload.result : undefined
  const uploadView =
    uploaded && (upload.display === 'Units' ? uploaded.units : uploaded.currency)
  const uploadUnit = upload.display === 'Units' ? uploaded?.file.unit_used : undefined
  // The currency view is converted on the server, so its options already
  // carry the right label; the explorer converts the same way.
  const uploadCurrency =
    upload.display === 'Currency' ? uploaded?.currency.currency : undefined
  const uploadOptions = uploadView?.explore_options ?? null
  const uploadFile = upload.file
  const fetchUpload = useCallback(
    (query: ExploreQuery) =>
      postExploreUpload(uploadFile!, { unit: uploadUnit, currency: uploadCurrency }, query),
    [uploadFile, uploadUnit, uploadCurrency],
  )

  // The explorer's filters start over for each file, unit and view, because
  // their ranges (dates, stakes, groupings) come from the data being explored.
  const uploadKey =
    uploadFile && uploadOptions
      ? `${uploadFile.name}:${uploadFile.size}:${uploadFile.lastModified}:${upload.display}:${uploadUnit}:${uploadCurrency}`
      : null
  const [uploadExplore, setUploadExplore] = useState<{
    key: string
    state: ExploreState
  } | null>(null)
  if (uploadKey && uploadOptions && uploadExplore?.key !== uploadKey) {
    setUploadExplore({ key: uploadKey, state: initialExploreState(uploadOptions) })
  }
  const updateUploadExplore = useCallback(
    (update: (s: ExploreState) => ExploreState) =>
      setUploadExplore((u) => (u === null ? u : { ...u, state: update(u.state) })),
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
                onCheck={onCheck}
                onRemove={onRemove}
              />
            )}
            {tab === 'explore' &&
              (upload.status === 'checking' ? (
                <div className="loading">Checking {upload.file?.name}…</div>
              ) : uploaded && !uploadOptions ? (
                <Alert kind="info" icon="📄">
                  No bet in {uploadFile?.name} was matched, so there is nothing to explore.
                  Remove it on the Upload tab to explore the full history again.
                </Alert>
              ) : uploaded && uploadOptions && uploadExplore?.key === uploadKey ? (
                <Explore
                  key={uploadKey}
                  state={uploadExplore.state}
                  setState={updateUploadExplore}
                  options={uploadOptions}
                  fetchExplore={fetchUpload}
                  fileName={uploadFile?.name}
                />
              ) : (
                explore && (
                  <Explore
                    key="history"
                    state={explore}
                    setState={updateExplore}
                    options={loaded.options}
                    fetchExplore={getExplore}
                  />
                )
              ))}
          </section>
        </>
      )}
    </main>
  )
}
