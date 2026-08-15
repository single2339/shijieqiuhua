import { afterEach, describe, expect, test, vi } from 'vitest'
import { fetchMatchDecision } from '../src/shijieqiuhua/api'

afterEach(() => {
  vi.restoreAllMocks()
})

const fixtureRequest = {
  home_team: '阿森纳',
  away_team: '热刺',
  kickoff_at: '2026-08-16T14:00:00+00:00',
  competition: '英超',
  provider: 'football-data',
  provider_match_id: 'match_1',
}

const decisionFixture = {
  outcome: 'home_win',
  outcome_probabilities: { home_win: 0.5, draw: 0.28, away_win: 0.22 },
  reason: '主队近期表现占优。',
  match: {
    home_team: '阿森纳', away_team: '热刺', kickoff_at: fixtureRequest.kickoff_at,
    competition: '英超', venue: '', profile: { competition_type: 'club', data_density: 'high', factor_pack: 'default' },
  },
  fixture_status: 'scheduled',
  model_prediction: {
    lean: 'home', summary: '主队近期表现占优。',
    outcome_probabilities: { home_win: 0.5, draw: 0.28, away_win: 0.22 },
    primary_probability: 0.5, margin_to_runner_up: 0.22, clarity: 'clear', scoreline_band: ['2-1'], drivers: [], uncertainties: [],
  },
  confidence: { level: 'L2', reason: '证据充分' },
  market_consensus: null,
  market_sources: [],
  market_comparison: { status: 'limited', model_leader: null, market_leader: null, leader_delta: null },
  evidence_summary: [],
  updated_at: '2026-08-15T10:00:00+00:00',
  actual_result: null,
  review: null,
  disclaimer: '仅供信息参考。',
}

describe('match decision API', () => {
  test('posts a fixture request to the decision endpoint without a question', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => decisionFixture })
    vi.stubGlobal('fetch', fetchMock)

    const decision = await fetchMatchDecision({
      ...fixtureRequest,
      question: '全场角球数预测是多少？',
    })

    expect(decision.model_prediction?.scoreline_band).toEqual(['2-1'])
    expect(fetchMock).toHaveBeenCalledWith('/api/football/osint/decisions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fixtureRequest),
    })
  })

  test.each([
    [401, '未登录'],
    [403, '需要付费权限'],
  ])('surfaces %i authorization errors from the decision endpoint', async (status, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status,
      text: async () => JSON.stringify({ detail: { message_zh: message } }),
    }))

    await expect(fetchMatchDecision(fixtureRequest)).rejects.toThrow(message)
  })
})
