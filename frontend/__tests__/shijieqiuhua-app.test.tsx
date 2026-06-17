import { renderToString } from 'react-dom/server'
import { describe, expect, test } from 'vitest'
import App from '../src/App'
import LandingPage from '../src/shijieqiuhua/components/LandingPage'

describe('shijieqiuhua app shell', () => {
  test('renders landing page by default (initial view)', () => {
    const html = renderToString(<App />)
    expect(html).toContain('世界球花')
    expect(html).toContain('把一场比赛')
    expect(html).toContain('不构成任何投注')
    expect(html).toContain('进入研判台')
  })

  test('landing page renders all core sections', () => {
    const html = renderToString(<LandingPage onEnter={() => {}} onRegister={() => {}} onLogin={() => {}} />)
    expect(html).toContain('不是预测，是研判')
    expect(html).toContain('看得见证据的结论')
    expect(html).toContain('按需选择')
    expect(html).toContain('情报通')
    expect(html).toContain('诚实的不确定性')
  })
})
