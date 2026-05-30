import type {
  AnalysisInterpretRequest,
  AnalysisInterpretResponse,
  AnomalyResult,
  AskRequest,
  AskResponse,
  CorroborationResult,
  DashboardData,
  DashboardStats,
  EntityGraphResult,
  GapAnalysisResult,
  ReportRequest,
  RiskHeatmapResult,
  SituationReport,
  SuperAnalysisRequest,
  SuperAnalysisResponse,
  TimelineResult,
} from './types'

export async function fetchDashboard(startDate?: string, endDate?: string): Promise<DashboardData> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  const url = qs ? `/api/dashboard?${qs}` : '/api/dashboard'
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function askQuestion(req: AskRequest): Promise<AskResponse> {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function fetchStats(startDate?: string, endDate?: string): Promise<DashboardStats> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  const url = qs ? `/api/stats?${qs}` : '/api/stats'
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function generateReport(req: ReportRequest): Promise<SituationReport> {
  const res = await fetch('/api/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

// ── Intelligence Analysis ──

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const qs = new URLSearchParams(params || {})
  const url = qs.toString() ? `${path}?${qs}` : path
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export function fetchTimeline(startDate?: string, endDate?: string, layer?: string, country?: string): Promise<TimelineResult> {
  const params: Record<string, string> = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  if (layer) params.layer = layer
  if (country) params.country = country
  return apiGet<TimelineResult>('/api/analysis/timeline', params)
}

export function fetchEntityGraph(): Promise<EntityGraphResult> {
  return apiGet<EntityGraphResult>('/api/analysis/entities')
}

export function fetchCorroboration(): Promise<CorroborationResult> {
  return apiGet<CorroborationResult>('/api/analysis/corroboration')
}

export function fetchAnomalies(startDate?: string, endDate?: string): Promise<AnomalyResult> {
  const params: Record<string, string> = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  return apiGet<AnomalyResult>('/api/analysis/anomalies', params)
}

export function fetchRiskHeatmap(): Promise<RiskHeatmapResult> {
  return apiGet<RiskHeatmapResult>('/api/analysis/risk-heatmap')
}

export function fetchGapAnalysis(): Promise<GapAnalysisResult> {
  return apiGet<GapAnalysisResult>('/api/analysis/gaps')
}

export async function interpretAnalysis(req: AnalysisInterpretRequest): Promise<AnalysisInterpretResponse> {
  const res = await fetch('/api/analysis/interpret', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function superAnalyze(req: SuperAnalysisRequest, signal?: AbortSignal): Promise<SuperAnalysisResponse> {
  const res = await fetch('/api/super-analysis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API error ${res.status}${text ? ': ' + text.slice(0, 200) : ''}`)
  }
  return res.json()
}
