// The last uploaded file, kept in this browser so a reload does not lose it.
//
// IndexedDB rather than localStorage: it stores the File itself, and an export
// can be several megabytes, past what localStorage holds. The file never
// leaves the viewer's machine this way — the server still keeps nothing — and
// it expires after UPLOAD_TTL_MS. Storage can be unavailable (a private
// window, blocked site data), so every call fails soft: the app then simply
// forgets the file on reload, as it did before.

export const UPLOAD_TTL_MS = 24 * 60 * 60 * 1000

const DB_NAME = 'sportmarket-analysis'
const STORE = 'upload'
const KEY = 'last'

export interface StoredUpload {
  file: File
  savedAt: number
  /** The unit the viewer set, or undefined for the file's typical stake. */
  unit?: number
}

/** Whether something saved at ``savedAt`` is still to be restored at ``now``. */
export function isFresh(savedAt: number, now: number): boolean {
  return now - savedAt >= 0 && now - savedAt < UPLOAD_TTL_MS
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function run<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest,
): Promise<T> {
  const db = await open()
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = action(db.transaction(STORE, mode).objectStore(STORE))
      request.onsuccess = () => resolve(request.result as T)
      request.onerror = () => reject(request.error)
    })
  } finally {
    db.close()
  }
}

export async function saveUpload(upload: StoredUpload): Promise<void> {
  try {
    await run('readwrite', (store) => store.put(upload, KEY))
  } catch {
    // Not kept across a reload; everything else still works.
  }
}

export async function loadUpload(now = Date.now()): Promise<StoredUpload | null> {
  try {
    const stored = await run<StoredUpload | undefined>('readonly', (store) =>
      store.get(KEY),
    )
    if (!stored) return null
    if (isFresh(stored.savedAt, now)) return stored
    await clearUpload()
    return null
  } catch {
    return null
  }
}

export async function clearUpload(): Promise<void> {
  try {
    await run('readwrite', (store) => store.delete(KEY))
  } catch {
    // Nothing stored, or nowhere to store it: either way nothing to remove.
  }
}
