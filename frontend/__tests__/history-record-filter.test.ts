import { describe, expect, it } from 'vitest'
import { dedupeHistoryRecords } from '../src/shijieqiuhua/historyRecords'
import type { HistoryRecord } from '../src/shijieqiuhua/types'

function record(overrides: Partial<HistoryRecord>): HistoryRecord {
  return {
    job_id: 'job-1',
    home_team: '科特迪瓦',
    away_team: '挪威',
    kickoff_at: '07-01 01:00',
    competition: '世界杯',
    predicted_lean: 'home',
    predicted_scoreline_band: ['1-0'],
    actual_home_score: 2,
    actual_away_score: 1,
    actual_outcome: 'home',
    lean_correct: true,
    scoreline_hit: false,
    settled_at: '2026-07-01T03:00:00Z',
    ...overrides,
  }
}

describe('dedupeHistoryRecords', () => {
  it('keeps only the first row for the same match with the same settled result', () => {
    const records = [
      record({ job_id: 'newest' }),
      record({ job_id: 'duplicate-older', predicted_lean: 'away' }),
      record({ job_id: 'same-match-different-score', actual_home_score: 1, actual_away_score: 1, actual_outcome: 'draw' }),
      record({ job_id: 'other-match', home_team: '法国', away_team: '瑞典' }),
    ]

    expect(dedupeHistoryRecords(records).map(r => r.job_id)).toEqual([
      'newest',
      'same-match-different-score',
      'other-match',
    ])
  })
})
