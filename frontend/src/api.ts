const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Source = { page: number; label: string; snippet: string; score: number }
export type UploadResult = { doc_id: string; filename: string; kind: string; pages: number; pages_processed: number; ocr_pages: number[]; truncated: boolean }
export type AskResult = { answer: string; sources: Source[] }
export type Turn = { role: 'user' | 'assistant'; text: string }

async function parse(res: Response) {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : ''
    throw new Error(body.message ?? (detail || (Array.isArray(body.detail) ? 'That request was not accepted. Please try again.' : 'Something went wrong. Please try again.')))
  }
  return body
}

const authHeader = (token?: string): Record<string, string> => (token ? { Authorization: `Bearer ${token}` } : {})

export async function upload(file: File, token?: string): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  return parse(await fetch(`${BASE}/upload`, { method: 'POST', body: form, headers: authHeader(token) }))
}

export async function ask(docIds: string[], question: string, history: Turn[], token?: string): Promise<AskResult> {
  return parse(
    await fetch(`${BASE}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify({ doc_ids: docIds, question, history }),
    }),
  )
}
