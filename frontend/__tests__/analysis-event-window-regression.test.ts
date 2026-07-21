import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const panelContent = readFileSync(resolve(__dirname, '../src/components/IntelAnalysisPanel.tsx'), 'utf-8')
const hookContent = readFileSync(resolve(__dirname, '../src/hooks/useAnalysisContext.ts'), 'utf-8')

describe('analysis event window regression', () => {
  test('analysis panel passes cross-day window to event workflow views', () => {
    expect(panelContent).toContain('buildAnalysisWindow')
    expect(panelContent).toContain('事件窗口')
    expect(panelContent).toContain('startDate={analysisWindow.startDate}')
    expect(panelContent).toContain('endDate={analysisWindow.endDate}')
  })

  test('analysis context fetches events and warnings with start/end dates instead of single-day date', () => {
    expect(hookContent).toContain('buildAnalysisWindow')
    expect(hookContent).toContain('fetchEventClusters({ startDate: analysisWindow.startDate, endDate: analysisWindow.endDate')
    expect(hookContent).toContain('fetchWarningIndicators({ startDate: analysisWindow.startDate, endDate: analysisWindow.endDate')
    expect(hookContent).not.toContain('date = startDate || endDate ?')
  })
})
