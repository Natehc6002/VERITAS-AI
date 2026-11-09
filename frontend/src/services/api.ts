import axios, { AxiosError } from 'axios'
import type {
  AnalysisBundle,
  CompareRequest,
  CompareResponse,
  DocumentListResponse,
  DocumentRecord,
  ExtractionResponse,
  EntityRecord,
  EvidenceRecord,
  FindingRecord,
  HealthResponse,
  StatsResponse,
} from '../types/api'

// Same-origin by default: the Vite dev server proxies /api to the backend.
// Set VITE_API_BASE to call the backend directly (CORS must allow the origin).
const BASE_URL: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
})

export interface UploadProgress {
  loaded: number
  total: number
}

/** Extract a human-readable message from any backend/network failure. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const ax = error as AxiosError<{ detail?: string | Array<{ msg?: string }> }>
    const detail = ax.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      // FastAPI validation errors
      return detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : 'Invalid request'))
        .join('; ')
    }
    if (ax.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
    if (!ax.response) return 'Cannot reach the backend. Make sure it is running on port 8000.'
    return `Request failed (${ax.response.status}).`
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred.'
}

export const documentsApi = {
  list: async (params: { page?: number; page_size?: number; search?: string } = {}) => {
    const { data } = await api.get<DocumentListResponse>('/api/v1/documents', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<DocumentRecord>(`/api/v1/documents/${id}`)
    return data
  },

  upload: async (
    file: File,
    onProgress?: (progress: UploadProgress) => void,
  ) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post<DocumentRecord>('/api/v1/documents/upload', form, {
      timeout: 300_000,
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress({ loaded: event.loaded, total: event.total })
        }
      },
    })
    return data
  },

  remove: async (id: string) => {
    const { data } = await api.delete<{ message: string }>(`/api/v1/documents/${id}`)
    return data
  },
}

export const analysisApi = {
  extract: async (id: string) => {
    const { data } = await api.post<ExtractionResponse>(`/api/v1/documents/${id}/extract`)
    return data
  },

  getText: async (id: string) => {
    const { data } = await api.get<ExtractionResponse>(`/api/v1/documents/${id}/text`)
    return data
  },

  analyze: async (id: string) => {
    const { data } = await api.post<AnalysisBundle>(`/api/v1/documents/${id}/analyze`)
    return data
  },

  getAnalysis: async (id: string) => {
    const { data } = await api.get<AnalysisBundle>(`/api/v1/documents/${id}/analysis`)
    return data
  },

  findings: async (id: string) => {
    const { data } = await api.get<FindingRecord[]>(`/api/v1/documents/${id}/findings`)
    return data
  },

  entities: async (id: string) => {
    const { data } = await api.get<EntityRecord[]>(`/api/v1/documents/${id}/entities`)
    return data
  },

  evidence: async (id: string) => {
    const { data } = await api.get<EvidenceRecord[]>(`/api/v1/documents/${id}/evidence`)
    return data
  },

  compare: async (payload: CompareRequest) => {
    const { data } = await api.post<CompareResponse>('/api/v1/compare', payload, {
      timeout: 300_000,
    })
    return data
  },

  stats: async () => {
    const { data } = await api.get<StatsResponse>('/api/v1/stats')
    return data
  },

  health: async () => {
    const { data } = await api.get<HealthResponse>('/api/v1/health')
    return data
  },
}
