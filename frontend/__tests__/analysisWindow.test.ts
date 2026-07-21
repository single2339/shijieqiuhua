import { describe, expect, test } from 'vitest'
import { buildAnalysisWindow } from '../src/utils/analysisWindow'

describe('buildAnalysisWindow', () => {
  test('defaults event analysis to a 14-day window ending on selected date', () => {
    const window = buildAnalysisWindow({ selectedDate: '2026-06-02' })

    expect(window.startDate).toBe('2026-05-20')
    expect(window.endDate).toBe('2026-06-02')
    expect(window.isExplicit).toBe(false)
  })

  test('anchors single-item analysis on the item capture date', () => {
    const window = buildAnalysisWindow({
      selectedDate: '2026-06-02',
      focusDate: '2026-05-27',
    })

    expect(window.startDate).toBe('2026-05-14')
    expect(window.endDate).toBe('2026-05-27')
  })

  test('respects explicit user date range', () => {
    const window = buildAnalysisWindow({
      selectedDate: '2026-06-02',
      startDate: '2026-05-01',
      endDate: '2026-05-31',
      focusDate: '2026-05-27',
    })

    expect(window.startDate).toBe('2026-05-01')
    expect(window.endDate).toBe('2026-05-31')
    expect(window.isExplicit).toBe(true)
  })

  test('uses selected date as the end when only explicit start date is set', () => {
    const window = buildAnalysisWindow({
      selectedDate: '2026-06-02',
      startDate: '2026-05-01',
    })

    expect(window.startDate).toBe('2026-05-01')
    expect(window.endDate).toBe('2026-06-02')
    expect(window.isExplicit).toBe(true)
  })
})
