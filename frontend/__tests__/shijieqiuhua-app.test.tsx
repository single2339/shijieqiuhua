import { renderToString } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import App, { decisionRequestKey, fixtureRequest, shouldChangeFixture, specialistQuestions } from '../src/App'
import LandingPage from '../src/shijieqiuhua/components/LandingPage'
import PostMatchReview from '../src/shijieqiuhua/components/PostMatchReview'
import ComparePanel from '../src/shijieqiuhua/components/ComparePanel'
import type { FootballMatch } from '../src/shijieqiuhua/types'

const match: FootballMatch = {
  id: 'fixture-1',
  league: '英超',
  kickoffAt: '2026-08-16T14:00:00+00:00',
  kickoffIso: '2026-08-16T14:00:00+00:00',
  homeTeam: '阿森纳',
  awayTeam: '热刺',
  provider: 'football-data',
  provider_match_id: 'match_1',
  home_provider_id: 'home_1',
  away_provider_id: 'away_1',
  publicLean: '未开赛',
  questions: [
    { id: 'goals', label: '赛果', prompt: '全场比分预测是多少？' },
    { id: 'corners', label: '角球', prompt: '全场角球数预测是多少？' },
    { id: 'fulltime', label: '全场赛果', prompt: '谁会赢？' },
  ],
}

describe('shijieqiuhua app shell', () => {
  test('renders landing page by default (initial view)', () => {
    const html = renderToString(<App />)
    expect(html).toContain('世界球花')
    expect(html).toContain('把一场比赛')
    expect(html).toContain('不构成任何投注')
    expect(html).toContain('进入研判台')
  })

  test('landing page renders all core sections', () => {
    const html = renderToString(<LandingPage onEnter={() => {}} onRegister={() => {}} onLogin={() => {}} />)
    expect(html).toContain('不是预测，是研判')
    expect(html).toContain('看得见证据的结论')
    expect(html).toContain('按需选择')
    expect(html).toContain('情报通')
    expect(html).toContain('诚实的不确定性')
  })
})

describe('match decision entry point', () => {
  test('builds the paid first-view request from fixture identity only', () => {
    expect(fixtureRequest(match)).toEqual({
      home_team: '阿森纳',
      away_team: '热刺',
      kickoff_at: '2026-08-16T14:00:00+00:00',
      competition: '英超',
      provider: 'football-data',
      provider_match_id: 'match_1',
      home_provider_id: 'home_1',
      away_provider_id: 'away_1',
    })
    expect(fixtureRequest(match)).not.toHaveProperty('question')
  })

  test('keeps full-time verdict out of specialist chips and exposes total goals separately', () => {
    const questions = specialistQuestions(match)

    expect(questions.map(item => item.id)).toEqual(['corners', 'total_goals'])
    expect(questions.map(item => item.label)).toContain('角球')
    expect(questions.map(item => item.label)).toContain('总进球')
  })

  test('does not restart a decision when the active fixture is clicked again', () => {
    expect(shouldChangeFixture('fixture-1', 'fixture-1')).toBe(false)
    expect(shouldChangeFixture('fixture-1', 'fixture-2')).toBe(true)
  })

  test('keeps the decision request key stable across a refreshed fixture object', () => {
    const refreshedMatch: FootballMatch = {
      ...match,
      questions: [...match.questions],
      publicLean: '进行中 1-0',
    }

    expect(refreshedMatch).not.toBe(match)
    expect(decisionRequestKey(refreshedMatch)).toBe(decisionRequestKey(match))
  })
})

describe('shijieqiuhua v2 review components', () => {
  const detail = {
    record: {
      job_id: 'fo_20260625_abcdef1234',
      home_team: '曼城',
      away_team: '利物浦',
      kickoff_at: '2026-06-25 19:00',
      competition: '英超',
      predicted_lean: 'home',
      predicted_scoreline_band: ['1-0', '2-1'],
      actual_home_score: 2,
      actual_away_score: 1,
      actual_outcome: 'home',
      lean_correct: true,
      scoreline_hit: true,
      settled_at: '2026-06-25 21:05',
    },
    retrospective: {
      hit_factors: ['近期状态'],
      miss_factors: ['秘密伤停'],
      note: '付费回顾注记',
    },
  }

  test('free post-match review does not render paid retrospective text into HTML', () => {
    const html = renderToString(<PostMatchReview detail={detail} loading={false} userTier="free" onUpgrade={() => {}} />)
    expect(html).toContain('开通后查看完整因子分析')
    expect(html).not.toContain('秘密伤停')
    expect(html).not.toContain('付费回顾注记')
  })

  test('paid post-match review renders scoreline band and retrospective text', () => {
    const html = renderToString(<PostMatchReview detail={detail} loading={false} userTier="paid" />)
    expect(html).toContain('1-0')
    expect(html).toContain('2-1')
    expect(html).toContain('近期状态')
    expect(html).toContain('付费回顾注记')
  })

  test('post-match review renders a stored Sporttery handicap settlement', () => {
    const handicapDetail = {
      ...detail,
      record: {
        ...detail.record,
        sporttery_handicap: {
          home_handicap: 1,
          predicted_outcome: 'draw',
          predicted_probability: 0.41,
          actual_outcome: 'draw',
          correct: true,
        },
      },
    }
    const html = renderToString(<PostMatchReview detail={handicapDetail} loading={false} userTier="free" />)

    expect(html).toContain('体彩让球（主队 +1）')
    expect(html).toContain('研判：让平（41%）')
    expect(html).toContain('赛果：让平')
    expect(html).toContain('命中')
  })

  test('compare panel renders insufficient evidence bucket', () => {
    const html = renderToString(
      <ComparePanel
        loading={false}
        onClose={() => {}}
        results={[{
          job_id: 'fo_20260625_abcdef1234',
          home_team: '曼城',
          away_team: '利物浦',
          predicted_lean: 'home',
          evidence_summary: { strong: 2, weak: 1, insufficient: 3 },
          factor_completeness: '2/4',
          top_uncertainties: [],
        }]}
      />,
    )
    expect(html).toContain('样本不足')
    expect(html).toContain('3')
  })
})
