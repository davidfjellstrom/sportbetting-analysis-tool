import type {
  ExploreOptions,
  ExploreQuery,
  ExploreResponse,
  OverviewResponse,
  UploadResponse,
} from './types'

// Same origin once deployed; the Vite dev server proxies /api to uvicorn.
const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(BASE + path, init)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // A body that is not JSON has nothing better to say than the status.
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export function getOverview(): Promise<OverviewResponse> {
  return request('/api/overview')
}

export function getExploreOptions(): Promise<ExploreOptions> {
  return request('/api/explore/options')
}

function queryString(query: ExploreQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v))
    else params.set(key, String(value))
  }
  return params.toString()
}

export function getExplore(query: ExploreQuery): Promise<ExploreResponse> {
  return request(`/api/explore?${queryString(query)}`)
}

/**
 * Explore an uploaded file. The server keeps nothing between requests, so the
 * file travels with every one. Without a unit the amounts are in the chosen
 * currency, converted at today's rate.
 */
export function postExploreUpload(
  file: File,
  choice: UploadChoice,
  query: ExploreQuery,
): Promise<ExploreResponse> {
  const body = uploadBody(file, choice)
  return request(`/api/explore/upload?${queryString(query)}`, { method: 'POST', body })
}

/** How an uploaded file is to be shown: a unit size, and a currency to convert
 * to at today's rate. Either left out means the file's own. */
export interface UploadChoice {
  unit?: number
  currency?: string
}

function uploadBody(file: File, { unit, currency }: UploadChoice): FormData {
  const body = new FormData()
  body.append('file', file, file.name)
  if (unit !== undefined) body.append('unit', String(unit))
  if (currency !== undefined) body.append('currency', currency)
  return body
}

export function postUpload(file: File, choice: UploadChoice = {}): Promise<UploadResponse> {
  return request('/api/upload', { method: 'POST', body: uploadBody(file, choice) })
}
