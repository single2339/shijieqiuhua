import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import ReportView from '../src/shijieqiuhua/components/ReportView'
import type { FootballOsintJob } from '../src/shijieqiuhua/types'

describe('ReportView probabilities', () => {
  test('renders exact outcome probabilities from the prediction contract', () => {
    const job = {
      prediction: {
        lean: 'home',
        summary: '主队略占优',
        outcome_probabilities: { home_win: 0.48, draw: 0.29, away_win: 0.23 },
        primary_probability: 0.48,
        margin_to_runner_up: 0.19,
        clarity: 'clear',
        scoreline_band: [],
        drivers: [],
        uncertainties: [],
        sporttery_market: null,
        handicap_conclusion: null,
      },
      confidence: null,
      intelligence_cycle: [],
      factors: [],
      evidence: [],
      confirmed_findings: [],
      assessments: [],
      alternative_explanations: [],
      next_steps: [],
    } as FootballOsintJob

    const html = renderToStaticMarkup(<ReportView osintJob={job} userTier="paid" />)

    expect(html).toContain('48')
    expect(html).toContain('29')
    expect(html).toContain('23')
  })
})
