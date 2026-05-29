const BASE = '/api'

export async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => apiFetch<HealthStatus>('/health'),
  documents: () => apiFetch<Document[]>('/documents'),
  document: (id: string) => apiFetch<DocumentDetail>(`/documents/${id}`),
  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return apiFetch<{ document_id: string; status: string }>('/documents/upload', {
      method: 'POST',
      body: fd,
    })
  },
  logs: (limit = 100) => apiFetch<SystemLog[]>(`/logs?limit=${limit}`),
  analytics: () => apiFetch<Analytics>('/analytics'),
}

export interface HealthStatus {
  status: string
  timestamp: string
  version: string
  services: {
    ocr: string
    openai: string
    anthropic: string
    gemini: string
  }
}

export interface Document {
  id: string
  filename: string
  file_hash: string
  upload_time: string
  file_size: number
  status: 'uploaded' | 'processing' | 'completed' | 'failed'
}

export interface OCRResult {
  id: string
  raw_text: string
  cleaned_text: string
  confidence_score: number
  processing_time: number
  created_at: string
}

export interface LLMAnalysis {
  id: string
  model_name: string
  prompt_type: string
  analysis_result: { analysis: string; processing_time: number; model_used: string }
  processing_time: number
  created_at: string
}

export interface DocumentDetail {
  document: Document
  ocr_results: OCRResult[]
  llm_analysis: LLMAnalysis[]
}

export interface SystemLog {
  id: string
  level: 'INFO' | 'WARNING' | 'ERROR'
  message: string
  component: string
  details: Record<string, unknown> | null
  created_at: string
}

export interface Analytics {
  document_stats: Record<string, number>
  ocr_metrics: { avg_confidence: number; avg_processing_time: number }
  llm_usage: Record<string, number>
  recent_activity: { uploads_24h: number }
}
