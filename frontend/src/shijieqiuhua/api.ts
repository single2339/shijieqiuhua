import type { FootballOsintJob, FootballOsintJobRequest, FootballQuestionAnswer } from './types'

const JSON_HEADER = { 'Content-Type': 'application/json' }

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`API error: ${res.status}${detail ? ` ${detail.slice(0, 160)}` : ''}`)
  }
  return res.json()
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

export async function fetchFootballOsintJob(jobId: string): Promise<FootballOsintJob> {
  const res = await fetch(`/api/football/osint/jobs/${encodeURIComponent(jobId)}`)
  return readJson<FootballOsintJob>(res)
}
