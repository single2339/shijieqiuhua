import type { CompareItem, FixtureStatus, FootballOsintJob, FootballOsintJobRequest, FootballQuestionAnswer, HistoryDetail, HistoryRecord, MatchDecision, TrackRecordStats } from './types'

const JSON_HEADER = { 'Content-Type': 'application/json' }

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

// FastAPI errors come back as { detail: <string | { message_zh, error_code }> }.
// Surface the human-readable Chinese message when present, else fall back.
async function readError(res: Response): Promise<string> {
  const raw = await res.text().catch(() => '')
  try {
    const body = JSON.parse(raw)
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (detail?.message_zh) return detail.message_zh
    if (detail?.error_code) return detail.error_code
  } catch {
    // not JSON — fall through to the raw text
  }
  return raw ? raw.slice(0, 160) : `请求失败（${res.status}）`
}

export async function createFootballOsintJob(request: FootballOsintJobRequest): Promise<FootballOsintJob> {
  const res = await fetch('/api/football/osint/jobs', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify(request),
  })
  return readJson<FootballOsintJob>(res)
}

export async function askFootballQuestion(request: FootballOsintJobRequest): Promise<FootballQuestionAnswer> {
  const res = await fetch('/api/football/osint/answer', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify(request),
  })
  return readJson<FootballQuestionAnswer>(res)
}

/**
 * Load the paid, first-view decision for a fixture.
 *
 * The server owns the full-time question. Dropping a caller's specialist
 * question keeps the first-view verdict independent of question UI state.
 */
export async function fetchMatchDecision(request: FootballOsintJobRequest): Promise<MatchDecision> {
  const { question: _question, ...fixtureRequest } = request
  const res = await fetch('/api/football/osint/decisions', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify(fixtureRequest),
  })
  return readJson<MatchDecision>(res)
}

export async function fetchFootballOsintJob(jobId: string): Promise<FootballOsintJob> {
  const res = await fetch(`/api/football/osint/jobs/${encodeURIComponent(jobId)}`)
  return readJson<FootballOsintJob>(res)
}

export async function fetchFixtures(days = 3): Promise<FixtureStatus[]> {
  const res = await fetch(`/api/football/osint/fixtures?days=${days}`)
  return readJson<FixtureStatus[]>(res)
}

export async function fetchTrackRecord(): Promise<TrackRecordStats> {
  const res = await fetch('/api/football/osint/track-record')
  return readJson<TrackRecordStats>(res)
}

// ── v2: history & compare ──

export async function fetchHistory(days = 30): Promise<HistoryRecord[]> {
  const res = await fetch(`/api/football/osint/history?days=${days}`)
  return readJson<HistoryRecord[]>(res)
}

export async function fetchHistoryDetail(jobId: string): Promise<HistoryDetail> {
  const res = await fetch(`/api/football/osint/history/${encodeURIComponent(jobId)}`)
  return readJson<HistoryDetail>(res)
}

export async function compareMatches(jobIds: string[]): Promise<CompareItem[]> {
  const res = await fetch('/api/football/osint/compare', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify({ job_ids: jobIds }),
  })
  return readJson<CompareItem[]>(res)
}

// ── auth ──

export interface AuthUser {
  id: number; username: string; email: string; role: string
  is_active: boolean; created_at: string; last_login_at: string
  entitlements: { type: string; granted_at: string; expires_at: string | null }[]
}

export async function getMe(): Promise<AuthUser | null> {
  const res = await fetch('/api/auth/me')
  if (!res.ok) return null
  return res.json()
}

export async function loginUser(username: string, password: string): Promise<AuthUser> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify({ username, password }),
  })
  return readJson<{ user: AuthUser }>(res).then(r => r.user)
}

export async function registerUser(username: string, password: string, inviteCode: string, email = ''): Promise<AuthUser> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: JSON_HEADER,
    body: JSON.stringify({ username, password, invite_code: inviteCode, email }),
  })
  return readJson<{ user: AuthUser }>(res).then(r => r.user)
}

export async function logoutUser(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' })
}

export interface RedeemResult { type: string; granted_at: string; expires_at: string | null; source: string }

export async function redeemCode(code: string): Promise<RedeemResult> {
  const res = await fetch('/api/billing/redeem', {
    method: 'POST', headers: JSON_HEADER, body: JSON.stringify({ code }),
  })
  return readJson<RedeemResult>(res)
}
