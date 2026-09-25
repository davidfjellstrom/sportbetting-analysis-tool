import { ApiError, postUpload, type UploadChoice } from '../api/client'
import type { DimensionKey, UploadResponse } from '../api/types'

export interface UploadState {
  file: File | null
  status: 'idle' | 'checking' | 'done' | 'error'
  error?: string
  result?: UploadResponse
  display: 'Units' | 'Currency'
  chosenCurrency: string
  unitText: string
  groupBy: DimensionKey
}

export const INITIAL_UPLOAD_STATE: UploadState = {
  file: null,
  status: 'idle',
  display: 'Units',
  chosenCurrency: 'EUR',
  unitText: '',
  groupBy: 'market_type',
}

// Currencies an uploader can label their file with. A file whose currency
// column names something else gets that added at the front of the list.
const DISPLAY_CURRENCIES = ['EUR', 'USD', 'SEK']

// Vercel rejects a request body above this before the API sees it; saying so
// here is clearer than a bare 413.
const MAX_UPLOAD_BYTES = 4.5 * 1024 * 1024

export function currencyOptions(result: UploadResponse): string[] {
  const fileCur = result.file.currency_in_file
  const options = DISPLAY_CURRENCIES.filter((c) => c !== fileCur)
  if (fileCur) options.unshift(fileCur)
  return options
}

function defaultUnitText(result: UploadResponse): string {
  return result.file.typical_stake === null ? '1.00' : result.file.typical_stake.toFixed(2)
}

/**
 * Check a file and put the outcome into the upload state. Resolves to whether
 * it was accepted, so the caller can keep it for the next reload. Lives outside
 * the Upload tab because a file restored on reload is checked before anyone
 * opens that tab.
 *
 * An empty ``choice`` is a fresh file and resets the viewer's choices; a unit
 * or a currency re-checks the same file and keeps the rest.
 */
export async function checkUpload(
  file: File,
  choice: UploadChoice,
  setState: (update: (s: UploadState) => UploadState) => void,
): Promise<boolean> {
  if (file.size > MAX_UPLOAD_BYTES) {
    setState((s) => ({
      ...s,
      file,
      status: 'error',
      result: undefined,
      error: `${file.name} is ${(file.size / 1024 / 1024).toFixed(2)} MB; files above 4.5 MB cannot be checked.`,
    }))
    return false
  }
  setState((s) => ({ ...s, file, status: 'checking', error: undefined }))
  try {
    const result = await postUpload(file, choice)
    setState((s) => ({
      ...s,
      status: 'done',
      result,
      chosenCurrency: result.currency.currency,
      unitText:
        choice.unit === undefined && choice.currency === undefined
          ? defaultUnitText(result)
          : result.file.unit_used.toFixed(2),
    }))
    return true
  } catch (error: unknown) {
    const message = error instanceof ApiError ? error.message : String(error)
    setState((s) =>
      // A re-check of the same file that fails — no exchange rate today, say —
      // keeps what was already shown and says why the choice did not apply.
      s.file === file && s.result
        ? { ...s, status: 'done', error: message }
        : { ...s, status: 'error', result: undefined, error: message },
    )
    return false
  }
}
