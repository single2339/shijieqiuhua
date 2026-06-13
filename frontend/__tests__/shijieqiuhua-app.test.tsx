import { renderToString } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import App from '../src/App'

describe('shijieqiuhua app shell', () => {
  test('renders the football question flow without access-control panels', () => {
    const html = renderToString(<App />)

    expect(html).toContain('世界球花')
    expect(html).toContain('继续问这场比赛')
    expect(html).not.toContain('邀请码')
    expect(html).not.toContain('付费码')
    expect(html).not.toContain('完整证据')
    expect(html).not.toContain('账号状态')
  })
})
