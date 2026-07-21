import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const panelContent = readFileSync(resolve(__dirname, '../src/components/SuperAnalysisPanel.tsx'), 'utf-8')
const hookContent = readFileSync(resolve(__dirname, '../src/hooks/useSuperAnalysis.ts'), 'utf-8')
const markdownContent = readFileSync(resolve(__dirname, '../src/lib/markdown.tsx'), 'utf-8')

describe('super analysis investigation contract', () => {
  test('submits selected playbook, scope, authorization, and verification depth', () => {
    expect(hookContent).toContain('investigation_type: investigationType')
    expect(hookContent).toContain('target')
    expect(hookContent).toContain('authorized')
    expect(hookContent).toContain('verification_depth: verificationDepth')
  })

  test('offers investigation controls and an explicit authorization gate for sensitive playbooks', () => {
    expect(panelContent).toContain('调查剧本')
    expect(panelContent).toContain('授权确认')
    expect(panelContent).toContain('验证深度')
    expect(panelContent).toContain('批准结论')
    expect(panelContent).toContain('需要补证')
    expect(panelContent).toContain('驳回结论')
    expect(hookContent).toContain('submitSuperAnalysisReview')
  })

  test('exports the traceable investigation ledger instead of only narrative output', () => {
    expect(markdownContent).toContain('证据账本')
    expect(markdownContent).toContain('关系网络')
    expect(markdownContent).toContain('时间线')
    expect(markdownContent).toContain('替代解释')
    expect(markdownContent).toContain('待核验项')
    expect(markdownContent).toContain('下一步核验任务')
    expect(markdownContent).toContain('分析师复核')
  })
})
