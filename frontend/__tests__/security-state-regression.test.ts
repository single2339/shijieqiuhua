import { describe, expect, test, vi } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { safeExternalUrl } from '../src/utils/safeUrl'
import {
  BRIEF_REPORT_HISTORY_STORAGE_KEY,
  BRIEF_WORKSPACE_STORAGE_KEY,
  clearUserScopedStorage,
  getUserStorageKey,
} from '../src/utils/userStorage'

const appContent = readFileSync(resolve(__dirname, '../src/App.tsx'), 'utf-8')
const authContent = readFileSync(resolve(__dirname, '../src/contexts/AuthContext.tsx'), 'utf-8')
const reportContent = readFileSync(resolve(__dirname, '../src/components/ReportPanel.tsx'), 'utf-8')
const dashboardHookContent = readFileSync(resolve(__dirname, '../src/hooks/useDashboardData.ts'), 'utf-8')
const superHookContent = readFileSync(resolve(__dirname, '../src/hooks/useSuperAnalysis.ts'), 'utf-8')
const analysisHookContent = readFileSync(resolve(__dirname, '../src/hooks/useAnalysisContext.ts'), 'utf-8')
const askContent = readFileSync(resolve(__dirname, '../src/components/AskPanel.tsx'), 'utf-8')
const statsContent = readFileSync(resolve(__dirname, '../src/components/StatsPanel.tsx'), 'utf-8')
const analysisViewContents = [
  'CorroborationView.tsx',
  'EventClustersView.tsx',
  'GapAnalysisView.tsx',
  'AIInterpretBadge.tsx',
  'SituationBriefView.tsx',
  'WarningIndicatorsView.tsx',
].map(file => readFileSync(resolve(__dirname, `../src/components/analysis/${file}`), 'utf-8'))
const externalLinkContents = [
  readFileSync(resolve(__dirname, '../src/lib/markdown.tsx'), 'utf-8'),
  readFileSync(resolve(__dirname, '../src/components/IntelCard.tsx'), 'utf-8'),
  readFileSync(resolve(__dirname, '../src/components/IntelAnalysisPanel.tsx'), 'utf-8'),
  readFileSync(resolve(__dirname, '../src/components/SuperAnalysisPanel.tsx'), 'utf-8'),
  readFileSync(resolve(__dirname, '../src/components/MapView.tsx'), 'utf-8'),
  readFileSync(resolve(__dirname, '../src/components/analysis/EventClustersView.tsx'), 'utf-8'),
  readFileSync(resolve(__dirname, '../src/components/analysis/SituationBriefView.tsx'), 'utf-8'),
]

describe('external URL validation', () => {
  test('accepts only absolute HTTP and HTTPS URLs', () => {
    expect(safeExternalUrl(' https://example.com/a ')).toBe('https://example.com/a')
    expect(safeExternalUrl('HTTP://example.com')).toBe('HTTP://example.com')
    expect(safeExternalUrl('javascript:alert(1)')).toBeUndefined()
    expect(safeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined()
    expect(safeExternalUrl('//example.com/path')).toBeUndefined()
    expect(safeExternalUrl('/internal/path')).toBeUndefined()
    expect(safeExternalUrl('')).toBeUndefined()
  })

  test('routes every frontend external-link renderer through the validator', () => {
    for (const content of externalLinkContents) {
      expect(content).toContain('safeExternalUrl')
    }
  })
})

describe('user-scoped browser state', () => {
  test('uses distinct storage keys for distinct authenticated users', () => {
    expect(getUserStorageKey(BRIEF_WORKSPACE_STORAGE_KEY, 7)).toBe('osint.briefWorkspace.v1.user.7')
    expect(getUserStorageKey(BRIEF_REPORT_HISTORY_STORAGE_KEY, 7)).toBe('osint.briefReportHistory.v1.user.7')
    expect(getUserStorageKey(BRIEF_WORKSPACE_STORAGE_KEY, 8)).not.toBe(getUserStorageKey(BRIEF_WORKSPACE_STORAGE_KEY, 7))
    expect(getUserStorageKey(BRIEF_WORKSPACE_STORAGE_KEY, null)).toBeNull()
  })

  test('clears both scoped and legacy report/workspace keys on logout', () => {
    const removeItem = vi.fn()
    vi.stubGlobal('window', { localStorage: { removeItem } })

    clearUserScopedStorage(7)

    expect(removeItem).toHaveBeenCalledWith('osint.briefWorkspace.v1.user.7')
    expect(removeItem).toHaveBeenCalledWith('osint.briefReportHistory.v1.user.7')
    expect(removeItem).toHaveBeenCalledWith(BRIEF_WORKSPACE_STORAGE_KEY)
    expect(removeItem).toHaveBeenCalledWith(BRIEF_REPORT_HISTORY_STORAGE_KEY)
    vi.unstubAllGlobals()
  })

  test('loads and writes workspace/history under the authenticated user and clears on logout', () => {
    expect(appContent).toContain('getUserStorageKey')
    expect(appContent).toContain('user?.id')
    expect(authContent).toContain('clearUserScopedStorage')
    expect(reportContent).toContain('userId')
    expect(reportContent).toContain('BRIEF_REPORT_HISTORY_STORAGE_KEY')
  })
})

describe('request cancellation and response generations', () => {
  test('dashboard requests carry abort controllers and update has_more from each page', () => {
    expect(dashboardHookContent).toContain('AbortController')
    expect(dashboardHookContent).toContain('requestGenerationRef')
    expect(dashboardHookContent).toContain('setHasMore(d.has_more)')
    expect(dashboardHookContent).toContain('hasMore,')
    expect(dashboardHookContent).toContain('collectControllerRef')
    expect(dashboardHookContent).toContain('collectRequestGenerationRef')
  })

  test('analysis context and every analysis view guard async responses by request generation', () => {
    expect(analysisHookContent).toContain('AbortController')
    expect(analysisHookContent).toContain('requestGenerationRef')
    for (const content of analysisViewContents) {
      expect(content).toContain('AbortController')
      expect(content).toContain('requestGenerationRef')
    }
  })

  test('other frontend request loops do not update state after cancellation or replacement', () => {
    expect(superHookContent).toContain('progressControllerRef')
    expect(superHookContent).toContain('requestGenerationRef')
    expect(askContent).toContain('AbortController')
    expect(askContent).toContain('requestGenerationRef')
    expect(statsContent).toContain('AbortController')
    expect(statsContent).toContain('requestGenerationRef')
    expect(authContent).toContain('authRequestGenerationRef')
  })
})
