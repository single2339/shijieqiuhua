import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const hookContent = readFileSync(resolve(__dirname, '../src/hooks/useDashboardData.ts'), 'utf-8')
const appContent = readFileSync(resolve(__dirname, '../src/App.tsx'), 'utf-8')
const cardContent = readFileSync(resolve(__dirname, '../src/components/IntelCard.tsx'), 'utf-8')

describe('dashboard refresh and intel card usability regressions', () => {
  test('poll refresh keeps feed items in sync with dashboard data', () => {
    expect(hookContent).not.toContain('if (!isPoll) {')
    expect(hookContent).toContain('setFeedItems(d.intel_items)')
    expect(hookContent).toContain('setFeedPage(1)')
  })

  test('load more does not race an active page-one refresh', () => {
    expect(hookContent).toContain('loadingMoreRef.current || requestControllerRef.current')
  })

  test('initial dashboard request is bounded to one page', () => {
    expect(hookContent).toContain('const PAGE_SIZE = 200')
    expect(hookContent).toContain('1, PAGE_SIZE, selectedDate')
    expect(hookContent).not.toContain('page_size=0')
  })

  test('map data grows with incrementally loaded feed pages', () => {
    expect(appContent).toContain('const mapItems = useMemo(() => feedItems.filter')
  })

  test('map module waits for browser idle time after data loads', () => {
    expect(appContent).toContain('requestIdleCallback')
    expect(appContent).toContain('globalThis.setTimeout')
    expect(appContent).toContain('cancelIdleCallback')
    expect(appContent).toContain('globalThis.clearTimeout')
    expect(appContent).toContain('!loading && mapReady')
  })

  test('desktop intel card remains compact and scrollable', () => {
    expect(cardContent).toContain("width: isMobile ? '100%' : 400")
    expect(cardContent).toContain("maxHeight: isMobile ? '78vh' : '66vh'")
    expect(cardContent).toContain('overflowY: \'auto\'')
  })
})
