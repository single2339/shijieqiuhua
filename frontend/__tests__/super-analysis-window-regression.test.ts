import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const appContent = readFileSync(resolve(__dirname, '../src/App.tsx'), 'utf-8')
const panelContent = readFileSync(resolve(__dirname, '../src/components/SuperAnalysisPanel.tsx'), 'utf-8')
const hookContent = readFileSync(resolve(__dirname, '../src/hooks/useSuperAnalysis.ts'), 'utf-8')

describe('super analysis window regression', () => {
  test('dashboard passes the active date window into the super analysis panel', () => {
    expect(appContent).toContain('<SuperAnalysisPanel')
    expect(appContent).toContain('startDate={startDate || selectedDate}')
    expect(appContent).toContain('endDate={endDate || selectedDate}')
  })

  test('super analysis submits the active date window to the backend', () => {
    expect(panelContent).toContain('startDate?: string')
    expect(panelContent).toContain('useSuperAnalysis({ startDate, endDate })')
    expect(hookContent).toContain('start_date: startDate')
    expect(hookContent).toContain('end_date: endDate')
  })
})
