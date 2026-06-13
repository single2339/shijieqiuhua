import { renderToString } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import App from '../src/App'

describe('shijieqiuhua app shell', () => {
  test('renders three-column layout with brand, paid user, and disclaimer', () => {
    const html = renderToString(<App />)
    expect(html).toContain('世界球花')
    expect(html).toContain('继续问这场比赛')
    expect(html).toContain('今日赛事')
    expect(html).toContain('问答历史')
    expect(html).toContain('已付费')
    expect(html).not.toContain('邀请码注册后继续')
    expect(html).toContain('不构成投注建议')
  })
})
