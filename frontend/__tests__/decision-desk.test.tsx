import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { describe, expect, test } from 'vitest'
import DecisionDesk from '../src/shijieqiuhua/components/DecisionDesk'
import type { MatchDecision } from '../src/shijieqiuhua/types'

function makeDecision(overrides: Partial<MatchDecision> = {}): MatchDecision {
  return {
    outcome: 'home_win',
    outcome_probabilities: { home_win: 0.53, draw: 0.25, away_win: 0.22 },
    reason: '主队近期稳定，主场表现形成优势。',
    fixture_status: 'scheduled',
    match: {
      home_team: '皇家社会',
      away_team: '塞维利亚',
      kickoff_at: '2026-08-18T19:00:00+08:00',
      competition: '西甲',
      venue: '阿诺埃塔球场',
      profile: { competition_type: 'league', data_density: 'high', factor_pack: 'standard' },
    },
    model_prediction: {
      lean: 'home',
      summary: '主队胜面稍高，但平局仍需纳入考虑。',
      outcome_probabilities: { home_win: 0.53, draw: 0.25, away_win: 0.22 },
      primary_probability: 0.53,
      margin_to_runner_up: 0.28,
      clarity: 'clear',
      scoreline_band: ['2-1', '1-0'],
      drivers: ['主场表现', '近期防守稳定'],
      uncertainties: ['临场首发'],
    },
    confidence: { level: 'L2', reason: '关键因子来源一致' },
    market_consensus: {
      status: 'consensus',
      fresh_source_count: 3,
      source_ids: ['sporttery', 'bet365', 'pinnacle'],
      probabilities: { home_win: 0.49, draw: 0.27, away_win: 0.24 },
    },
    market_sources: [
      {
        source_id: 'sporttery',
        display_name: '中国体育彩票',
        market: '1x2',
        odds: { home_win: 1.93, draw: 3.31, away_win: 4.04 },
        implied_probabilities: { home_win: 0.5, draw: 0.28, away_win: 0.22 },
        observed_at: '2026-08-18T08:15:00Z',
        provider_event_id: 'sp-123',
      },
      {
        source_id: 'bet365',
        display_name: 'Bet365',
        market: '1x2',
        odds: { home_win: 1.98, draw: 3.3, away_win: 3.9 },
        observed_at: '2026-08-18T08:12:00Z',
        provider_event_id: 'odds-456',
      },
    ],
    market_comparison: {
      status: 'aligned',
      model_leader: 'home_win',
      market_leader: 'home_win',
      leader_delta: 0.04,
    },
    evidence_summary: [],
    updated_at: '2026-08-18T08:20:00Z',
    disclaimer: '预测仅供信息参考，不构成任何建议。',
    ...overrides,
  }
}

describe('DecisionDesk', () => {
  test('puts the system verdict and predicted score before market detail', () => {
    const html = renderToStaticMarkup(<DecisionDesk decision={makeDecision()} />)

    expect(html).toContain('系统研判')
    expect(html).toContain('主胜方向')
    expect(html).toContain('预测比分')
    expect(html).toContain('2-1')
    expect(html).toContain('市场共识')
    expect(html.indexOf('系统研判')).toBeLessThan(html.indexOf('市场共识'))
    expect(html).toContain('中国体育彩票')
    expect(html).toContain('Bet365')
    expect(html).toContain('模型与市场方向一致')
  })

  test('shows a market fallback instead of fabricating consensus', () => {
    const decision = makeDecision({
      market_consensus: { status: 'insufficient_sources', fresh_source_count: 1, source_ids: ['sporttery'] },
      market_sources: [],
      market_comparison: { status: 'limited' },
    })
    const html = renderToStaticMarkup(<DecisionDesk decision={decision} />)

    expect(html).toContain('市场共识暂不可用')
    expect(html).toContain('仅获得 1 个新鲜来源')
    expect(html).toContain('暂不比较模型与市场')
  })

  test('renders the final score and review when the fixture is finished', () => {
    const html = renderToStaticMarkup(<DecisionDesk decision={makeDecision({
      fixture_status: 'finished',
      actual_result: { home_score: 2, away_score: 0, outcome: 'home', settled_at: '2026-08-18T12:00:00Z' },
      review: { lean_correct: true, scoreline_hit: false, summary: '方向命中，比分未命中。' },
    })} />)

    expect(html).toContain('赛后回看')
    expect(html).toContain('最终比分')
    expect(html).toContain('2 - 0')
    expect(html).toContain('方向命中')
    expect(html).toContain('比分未命中')
    expect(html.indexOf('最终比分')).toBeLessThan(html.indexOf('系统研判'))
  })

  test('marks stale market snapshots and keeps live fixtures as a pre-match verdict', () => {
    const stale = makeDecision({
      fixture_status: 'live',
      market_sources: [{
        source_id: 'sporttery', display_name: '中国体育彩票', market: '1x2',
        odds: { home_win: 1.93, draw: 3.31, away_win: 4.04 },
        observed_at: new Date(Date.now() - 31 * 60_000).toISOString(), provider_event_id: 'sp-123',
      }],
    })
    const html = renderToStaticMarkup(<DecisionDesk decision={stale} />)

    expect(html).toContain('赛前研判，截至开赛前')
    expect(html).toContain('数据已过期')
  })

  test('uses a one-column probability layout on mobile', () => {
    const css = readFileSync(new URL('../src/shijieqiuhua.css', import.meta.url), 'utf8')
    expect(css).toContain('@media (max-width: 860px)')
    expect(css).toContain('.sqh-decision-probabilities { grid-template-columns: 1fr; }')
  })

  test('provides a structured skeleton and an inline error state', () => {
    const loading = renderToStaticMarkup(<DecisionDesk loading />)
    const failed = renderToStaticMarkup(<DecisionDesk error="决策数据暂时不可用" />)

    expect(loading).toContain('sqh-decision-skeleton')
    expect(failed).toContain('决策数据暂时不可用')
    expect(failed).toContain('sqh-decision-state--error')
  })
})
