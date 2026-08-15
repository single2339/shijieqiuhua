import { describe, expect, test } from 'vitest'
import { formatBestLeanSummary, formatTrackRecordSummary } from '../src/shijieqiuhua/components/LandingPage'
import type { TrackRecordStats } from '../src/shijieqiuhua/types'

describe('formatTrackRecordSummary', () => {
  test('returns null when sample is below threshold (no recent field)', () => {
    const stats: TrackRecordStats = { settled: 5 }
    expect(formatTrackRecordSummary(stats)).toBeNull()
  })

  test('formats a summary string once accuracy fields are present', () => {
    const stats: TrackRecordStats = {
      settled: 124, lean_accuracy: 0.68, scoreline_accuracy: 0.21, recent: [],
    }
    expect(formatTrackRecordSummary(stats)).toBe('近 124 场比赛 · 方向命中率 68% · 比分命中率 21%')
  })

  test('formats the best-performing lean including double chance', () => {
    const stats: TrackRecordStats = {
      settled: 22,
      lean_accuracy: 0.77,
      scoreline_accuracy: 0.18,
      best_lean: { lean: 'home_or_draw', settled: 9, accuracy: 0.889 },
      recent: [],
    }
    expect(formatBestLeanSummary(stats)).toBe('胜率最高：主胜或平 · 9 场命中率 89%')
  })
})
