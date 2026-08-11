import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import ReportView from '../src/shijieqiuhua/components/ReportView'
import type { FootballOsintJob } from '../src/shijieqiuhua/types'

function makeJob(overrides: Partial<FootballOsintJob['prediction']> = {}): FootballOsintJob {
  return {
    prediction: {
      lean: 'home',
      summary: '首选主胜，模型与公开信息支持主队，领先 21 个百分点。',
      outcome_probabilities: { home_win: 0.48, draw: 0.27, away_win: 0.25 },
      primary_probability: 0.48,
      margin_to_runner_up: 0.21,
      clarity: 'clear',
      scoreline_band: ['1-0', '2-1'],
      drivers: ['近期状态', '主场优势', '不应显示'],
      uncertainties: [],
      sporttery_market: {
        provider: 'sporttery',
        had_odds: null,
        had_implied_probabilities: { home_win: 0.4, draw: 0.3, away_win: 0.3 },
        home_handicap: 1,
        hhad_odds: { home_win: 2.1, draw: 3.2, away_win: 3.4 },
        hhad_implied_probabilities: { home_win: 0.4, draw: 0.35, away_win: 0.25 },
        observed_at: '2026-08-12T08:00:00Z',
      },
      handicap_conclusion: {
        home_handicap: 1,
        outcome: 'draw',
        handicap_probabilities: { home_win: 0.33, draw: 0.41, away_win: 0.26 },
        probability: 0.41,
        margin_to_runner_up: 0.08,
        clarity: 'clear',
      },
      ...overrides,
    },
    confidence: { level: 'L2', reason: '多源一致' },
    intelligence_cycle: [{ name: '收集', status: 'completed', summary: '付费过程内容' }],
    factors: [{ factor_id: 'form', label: '付费敏感因子', group: 'form', enabled: true, weight: 1, impact: 0.2, direction: 'home', confidence: 0.8, evidence_ids: [], missing_reason: '' }],
    evidence: [],
    confirmed_findings: [],
    assessments: [],
    alternative_explanations: [],
    next_steps: [],
  } as FootballOsintJob
}

describe('ReportView concise verdict', () => {
  test('renders ranked exact probabilities, Sporttery reference, and a closed paid disclosure', () => {
    const html = renderToStaticMarkup(<ReportView osintJob={makeJob({ lean: 'away_or_draw' })} userTier="paid" />)

    expect(html).toContain('主胜 48%')
    expect(html).toContain('平局 27%')
    expect(html).toContain('客胜 25%')
    expect(html).toContain('首选主胜 · 领先 21 个百分点')
    expect(html).toContain('data-lead="true"')
    expect(html).toContain('sqh-prob-cell--lead" data-lead="true"><span class="sqh-prob-label">主胜 48%')
    expect(html).toContain('体彩官方盘口参考')
    expect(html).toContain('主队受让 +1')
    expect(html).toContain('让平 · 41%')
    expect(html).toContain('查看完整分析过程')
    expect(html).toContain('<details class="sqh-analysis-disclosure">')
    expect(html).not.toContain('open=""')
    expect(html).not.toContain('不应显示')
  })

  test('keeps close outcomes explicitly close', () => {
    const html = renderToStaticMarkup(<ReportView osintJob={makeJob({
      summary: '首选主胜，但与平局接近，优势不足。',
      outcome_probabilities: { home_win: 0.35, draw: 0.33, away_win: 0.32 },
      primary_probability: 0.35,
      margin_to_runner_up: 0.02,
      clarity: 'close',
    })} userTier="paid" />)

    expect(html).toContain('优势不足，存在接近结果')
    expect(html).not.toContain('明确')
  })

  test('does not render a Sporttery reference without a market', () => {
    const html = renderToStaticMarkup(<ReportView osintJob={makeJob({ sporttery_market: null, handicap_conclusion: null })} userTier="paid" />)

    expect(html).not.toContain('体彩官方盘口参考')
  })

  test('does not place paid process content in free HTML', () => {
    const html = renderToStaticMarkup(<ReportView osintJob={makeJob()} userTier="free" />)

    expect(html).toContain('开通完整功能后查看')
    expect(html).not.toContain('付费过程内容')
    expect(html).not.toContain('付费敏感因子')
    expect(html).not.toContain('查看完整分析过程')
  })
})
