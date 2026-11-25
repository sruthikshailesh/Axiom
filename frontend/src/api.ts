/** Typed access to the AXIOM backend. The browser never sees an LLM key. */

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(
  /\/+$/,
  '',
)

export interface SourceSummary {
  id: number
  title: string
  filename: string
  doc_date: string | null
  author: string | null
  uploaded_at: string
  chunk_count: number
}

export interface Chunk {
  id: number
  source_id: number
  position: number
  text: string
}

export interface RunSummary {
  id: number
  status: string
}

export type ClaimStatus = 'verified' | 'conflict' | 'uncertain' | 'superseded'

export interface Evidence {
  chunk_id: number
  source_id: number
  source_title: string
  quote: string
  role: 'supports' | 'contradicts'
}

export interface Claim {
  id: number
  text: string
  claim_date: string | null
  owner: string | null
  status: ClaimStatus
  confidence: number
  uncertainty_note: string | null
  evidence: Evidence[]
}

export interface Conflict {
  claim_a_id: number
  claim_b_id: number
  reason: string
}

export interface Supersession {
  old_claim_id: number
  new_claim_id: number
  reason: string
}

export interface RunDetail {
  id: number
  question: string
  status: string
  demo: boolean
  error: string | null
  created_at: string
  finished_at: string | null
  claims: Claim[]
  conflicts: Conflict[]
  supersessions: Supersession[]
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) {
        const record = item as { msg?: unknown; loc?: unknown }
        const loc = Array.isArray(record.loc)
          ? record.loc.filter((part) => part !== 'body').join('.')
          : ''
        return loc ? `${loc}: ${String(record.msg)}` : String(record.msg)
      }
      return String(item)
    })
    return parts.join('; ') || null
  }
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, init)
  } catch {
    throw new Error(`Cannot reach the AXIOM backend at ${API_URL}. Is uvicorn running?`)
  }

  if (!response.ok) {
    let detail: unknown = null
    try {
      detail = (await response.json())?.detail
    } catch {
      detail = null
    }
    const message =
      detailMessage(detail) ?? `Request failed (${response.status} ${response.statusText}).`
    throw new Error(message)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function listSources(): Promise<SourceSummary[]> {
  return request<SourceSummary[]>('/sources')
}

export function uploadSource(
  file: File,
  title?: string,
  docDate?: string,
  author?: string,
): Promise<{ id: number; title: string; chunk_count: number }> {
  const body = new FormData()
  body.append('file', file)
  if (title) body.append('title', title)
  if (docDate) body.append('doc_date', docDate)
  if (author) body.append('author', author)
  return request('/sources', { method: 'POST', body })
}

export function listChunks(sourceId: number): Promise<Chunk[]> {
  return request<Chunk[]>(`/sources/${sourceId}/chunks`)
}

export function startRun(question: string): Promise<RunSummary> {
  return request<RunSummary>('/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export function startDemoRun(): Promise<RunSummary & { demo: boolean }> {
  return request<RunSummary & { demo: boolean }>('/demo/run', { method: 'POST' })
}

export function getRun(id: number): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${id}`)
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Something went wrong.'
}
