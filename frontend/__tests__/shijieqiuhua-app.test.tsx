import { renderToString } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import App from '../src/App'

describe('shijieqiuhua app shell', () => {
  test('renders brand, match rail, and disclaimer in initial auth-loading state', () => {
    const html = renderToString(<App />)
    // brand always visible
    expect(html).toContain('世界球花')
    // left rail always visible; starts in loading state (no mock data)
    expect(html).toContain('今日赛事')
    expect(html).toContain('加载中')
    // disclaimer always visible
    expect(html).toContain('不构成投注建议')
    // middle panel: no match data during loading → empty state
    expect(html).toContain('暂无赛事数据')
  })
})
