import type {
  AdminStats,
  AdminUserDetail,
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
  InviteCodeInfo,
  LoginResponse,
  ReportRequest,
  RiskHeatmapResult,
  SituationReport,
  SuperAnalysisRequest,
  SuperAnalysisResponse,
  TimelineResult,
  UserInfo,
} from './types'

const JSON_HEADER = { 'Content-Type': 'application/json' }

async function safeGet<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function safePost<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API error ${res.status}${text ? ': ' + text.slice(0, 200) : ''}`)
  }
  return res.json()
}

async function safePostWithDetail<T>(url: string, body: unknown, fallbackMsg: string): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || fallbackMsg)
  }
  return res.json()
}

export async function fetchDashboard(startDate?: string, endDate?: string, page?: number, pageSize?: number, date?: string): Promise<DashboardData> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  if (page) params.set('page', String(page))
  if (pageSize) params.set('page_size', String(pageSize))
  if (date) params.set('date', date)
  const qs = params.toString()
  const url = qs ? `/api/dashboard?${qs}` : '/api/dashboard'
  return safeGet<DashboardData>(url)
}

export function askQuestionIntel(req: AskRequest, signal?: AbortSignal): Promise<AskResponse> {
  return safePost<AskResponse>('/api/intel/ask', req, signal)
}

export function fetchStats(startDate?: string, endDate?: string): Promise<DashboardStats> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  const url = qs ? `/api/stats?${qs}` : '/api/stats'
  return safeGet<DashboardStats>(url)
}

export function generateReportIntel(req: ReportRequest, signal?: AbortSignal): Promise<SituationReport> {
  return safePost<SituationReport>('/api/intel/report', req, signal)
}

// ── Intelligence Analysis ──

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const qs = new URLSearchParams(params || {})
  const url = qs.toString() ? `${path}?${qs}` : path
  return safeGet<T>(url)
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

export function interpretAnalysis(req: AnalysisInterpretRequest): Promise<AnalysisInterpretResponse> {
  return safePost<AnalysisInterpretResponse>('/api/intel/interpret', req)
}

export function superAnalyze(req: SuperAnalysisRequest, signal?: AbortSignal): Promise<SuperAnalysisResponse> {
  return safePost<SuperAnalysisResponse>('/api/intel/super-analysis', req, signal)
}

export interface SuperAnalysisProgress {
  phase: string
  message: string
  percent: number
  elapsed_seconds: number
  detail: Record<string, unknown>
}

export async function fetchSuperAnalysisProgress(): Promise<SuperAnalysisProgress> {
  const res = await fetch('/api/super-analysis/progress')
  if (!res.ok) throw new Error(`Progress API error: ${res.status}`)
  return res.json()
}

// ── Auth API ──

export function loginUser(username: string, password: string): Promise<LoginResponse> {
  return safePostWithDetail<LoginResponse>('/api/auth/login', { username, password }, '登录失败')
}

export function registerUser(username: string, email: string, password: string, inviteCode: string): Promise<LoginResponse> {
  return safePostWithDetail<LoginResponse>(
    '/api/auth/register',
    { username, email, password, invite_code: inviteCode },
    '注册失败',
  )
}

export async function fetchCurrentUser(): Promise<UserInfo> {
  const res = await fetch('/api/auth/me')
  if (!res.ok) throw new Error('会话已过期')
  return res.json()
}

export async function logoutUser(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', headers: JSON_HEADER }).catch(() => {})
}

// ── Admin API ──

export async function fetchAdminUsers(): Promise<AdminUserDetail[]> {
  const res = await fetch('/api/admin/users')
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '获取用户列表失败')
  }
  const data = await res.json()
  return data.users ?? data
}

export async function updateAdminUser(userId: number, updates: { is_active?: boolean; role?: string }): Promise<void> {
  const res = await fetch(`/api/admin/users/${userId}`, {
    method: 'PUT',
    headers: JSON_HEADER,
    body: JSON.stringify(updates),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '更新用户失败')
  }
}

export async function fetchAdminInviteCodes(): Promise<InviteCodeInfo[]> {
  const res = await fetch('/api/admin/invite-codes')
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '获取邀请码失败')
  }
  return res.json()
}

export async function createAdminInviteCodes(count: number, maxUses: number): Promise<InviteCodeInfo[]> {
  const res = await fetch('/api/admin/invite-codes', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify({ count, max_uses: maxUses }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '生成邀请码失败')
  }
  const data = await res.json()
  return data.codes ?? data
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const res = await fetch('/api/admin/stats')
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '获取统计数据失败')
  }
  return res.json()
}
