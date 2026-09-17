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

export function getExplore(query: ExploreQuery): Promise<ExploreResponse> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v))
    else params.set(key, String(value))
  }
  return request(`/api/explore?${params}`)
}

export function postUpload(file: File, unit?: number): Promise<UploadResponse> {
  const body = new FormData()
  body.append('file', file, file.name)
  if (unit !== undefined) body.append('unit', String(unit))
  return request('/api/upload', { method: 'POST', body })
}
