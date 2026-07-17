import type {
  AdminStats,
  AdminUserDetail,
  AnalysisInterpretRequest,
  AnalysisInterpretResponse,
  AskRequest,
  AskResponse,
  CorroborationResult,
  DashboardData,
  DashboardStats,
  EventClusterResult,
  GapAnalysisResult,
  InviteCodeInfo,
  ReportRequest,
  SituationReport,
  SituationBriefResult,
  SuperAnalysisRequest,
  SuperAnalysisResponse,
  WarningIndicatorResult,
} from './types'

const JSON_HEADER = { 'Content-Type': 'application/json' }

async function safeGet<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = signal ? await fetch(url, { signal }) : await fetch(url)
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

export async function fetchDashboard(startDate?: string, endDate?: string, page?: number, pageSize?: number, date?: string, signal?: AbortSignal): Promise<DashboardData> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  if (page) params.set('page', String(page))
  if (pageSize !== undefined) params.set('page_size', String(pageSize))
  if (date) params.set('date', date)
  const qs = params.toString()
  const url = qs ? `/api/dashboard?${qs}` : '/api/dashboard'
  return safeGet<DashboardData>(url, signal)
}

export function askQuestionIntel(req: AskRequest, signal?: AbortSignal): Promise<AskResponse> {
  return safePost<AskResponse>('/api/intel/ask', req, signal)
}

export function fetchStats(startDate?: string, endDate?: string, signal?: AbortSignal): Promise<DashboardStats> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  const url = qs ? `/api/stats?${qs}` : '/api/stats'
  return safeGet<DashboardStats>(url, signal)
}

export function generateReportIntel(req: ReportRequest, signal?: AbortSignal): Promise<SituationReport> {
  return safePost<SituationReport>('/api/intel/report', req, signal)
}

// ── Intelligence Analysis ──

async function apiGet<T>(path: string, params?: Record<string, string>, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams(params || {})
  const url = qs.toString() ? `${path}?${qs}` : path
  return safeGet<T>(url, signal)
}

export function fetchCorroboration(params?: {
  date?: string
  startDate?: string
  endDate?: string
  layers?: string[]
  country?: string
}, signal?: AbortSignal): Promise<CorroborationResult> {
  const query: Record<string, string> = {}
  if (params?.date) query.date = params.date
  if (params?.startDate) query.start_date = params.startDate
  if (params?.endDate) query.end_date = params.endDate
  if (params?.layers?.length) query.layers = params.layers.join(',')
  if (params?.country) query.country = params.country
  return apiGet<CorroborationResult>('/api/analysis/corroboration', query, signal)
}

export function fetchGapAnalysis(params?: {
  date?: string
  startDate?: string
  endDate?: string
  layers?: string[]
  country?: string
}, signal?: AbortSignal): Promise<GapAnalysisResult> {
  const query: Record<string, string> = {}
  if (params?.date) query.date = params.date
  if (params?.startDate) query.start_date = params.startDate
  if (params?.endDate) query.end_date = params.endDate
  if (params?.layers?.length) query.layers = params.layers.join(',')
  if (params?.country) query.country = params.country
  return apiGet<GapAnalysisResult>('/api/analysis/gaps', query, signal)
}

export function fetchSituationBrief(params: {
  date?: string
  startDate?: string
  endDate?: string
  layers?: string[]
  country?: string
}, signal?: AbortSignal): Promise<SituationBriefResult> {
  const query: Record<string, string> = {}
  if (params.date) query.date = params.date
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.layers?.length) query.layers = params.layers.join(',')
  if (params.country) query.country = params.country
  return apiGet<SituationBriefResult>('/api/analysis/brief', query, signal)
}

export function fetchEventClusters(params: {
  date?: string
  startDate?: string
  endDate?: string
  layers?: string[]
  country?: string
}, signal?: AbortSignal): Promise<EventClusterResult> {
  const query: Record<string, string> = {}
  if (params.date) query.date = params.date
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.layers?.length) query.layers = params.layers.join(',')
  if (params.country) query.country = params.country
  return apiGet<EventClusterResult>('/api/analysis/events', query, signal)
}

export function fetchWarningIndicators(params: {
  date?: string
  startDate?: string
  endDate?: string
  layers?: string[]
  country?: string
}, signal?: AbortSignal): Promise<WarningIndicatorResult> {
  const query: Record<string, string> = {}
  if (params.date) query.date = params.date
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.layers?.length) query.layers = params.layers.join(',')
  if (params.country) query.country = params.country
  return apiGet<WarningIndicatorResult>('/api/analysis/warnings', query, signal)
}

export function interpretAnalysis(req: AnalysisInterpretRequest, signal?: AbortSignal): Promise<AnalysisInterpretResponse> {
  return safePost<AnalysisInterpretResponse>('/api/intel/interpret', req, signal)
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

export function shouldApplySuperAnalysisProgress(progress: SuperAnalysisProgress): boolean {
  return progress.phase !== 'idle'
}

export async function fetchSuperAnalysisProgress(requestId?: string, signal?: AbortSignal): Promise<SuperAnalysisProgress> {
  const url = requestId ? `/api/super-analysis/progress?request_id=${encodeURIComponent(requestId)}` : '/api/super-analysis/progress'
  const res = signal ? await fetch(url, { signal }) : await fetch(url)
  if (!res.ok) throw new Error(`Progress API error: ${res.status}`)
  return res.json()
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

// ── Auth helpers ──

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  const res = await fetch('/api/auth/me/change-password', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '修改密码失败')
  }
}

export async function resetUserPassword(userId: number, newPassword: string): Promise<void> {
  const res = await fetch(`/api/admin/users/${userId}/reset-password`, {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify({ new_password: newPassword }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || '重置密码失败')
  }
}
