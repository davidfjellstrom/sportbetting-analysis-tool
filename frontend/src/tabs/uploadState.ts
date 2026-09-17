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
