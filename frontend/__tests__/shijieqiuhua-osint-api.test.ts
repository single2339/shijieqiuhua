import { afterEach, describe, expect, test, vi } from 'vitest'
import { askFootballQuestion, createFootballOsintJob, fetchFootballOsintJob, fetchTrackRecord } from '../src/shijieqiuhua/api'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('shijieqiuhua football osint api', () => {
  test('creates a football osint job with match details', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: 'fo_1',
        status: 'completed',
        phase: 'done',
        progress: 100,
        match: { home_team: 'Japan U23', away_team: 'Korea U23', profile: { competition_type: 'u23' } },
        sources: [],
        evidence: [],
        factors: [],
        prediction: null,
        confidence: null,
        report_markdown: '',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const job = await createFootballOsintJob({
      home_team: 'Japan U23',
      away_team: 'Korea U23',
      kickoff_at: '2026-06-08 18:00',
      competition: 'AFC U23 Asian Cup',
      question: '角球会不会偏多？',
    })

    expect(job.job_id).toBe('fo_1')
    expect(fetchMock).toHaveBeenCalledWith('/api/football/osint/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        home_team: 'Japan U23',
        away_team: 'Korea U23',
        kickoff_at: '2026-06-08 18:00',
        competition: 'AFC U23 Asian Cup',
        question: '角球会不会偏多？',
      }),
    })
  })

  test('fetches an existing football osint job', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 'fo_2', status: 'running', phase: 'collect', progress: 40 }),
    }))

    const job = await fetchFootballOsintJob('fo_2')

    expect(job.status).toBe('running')
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/football/osint/jobs/fo_2')
  })

  test('asks a simplified football question answer', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        related: true,
        analysis_started: true,
        answer: '倾向主队不败。',
        judgment: 'home_or_draw',
        reasons: ['近期状态信号'],
        confidence_level: 'L3',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const answer = await askFootballQuestion({
      home_team: 'Japan U23',
      away_team: 'Korea U23',
      kickoff_at: '2026-06-08 18:00',
      competition: 'AFC U23 Asian Cup',
      question: '这场怎么看？',
    })

    expect(answer.answer).toBe('倾向主队不败。')
    expect(fetchMock).toHaveBeenCalledWith('/api/football/osint/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        home_team: 'Japan U23',
        away_team: 'Korea U23',
        kickoff_at: '2026-06-08 18:00',
        competition: 'AFC U23 Asian Cup',
        question: '这场怎么看？',
      }),
    })
  })

  test('fetches track record stats', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ settled: 30, lean_accuracy: 0.6, scoreline_accuracy: 0.2, recent: [] }),
    }))

    const stats = await fetchTrackRecord()

    expect(stats.settled).toBe(30)
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/football/osint/track-record')
  })
})
