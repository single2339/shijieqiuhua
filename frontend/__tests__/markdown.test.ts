import { describe, test, expect } from 'vitest'
import { parseAnalysis, generateMarkdown } from '../src/lib/markdown'

describe('parseAnalysis', () => {
  test('parses h2 headings', () => {
    const blocks = parseAnalysis('## 测试标题\n内容')
    expect(blocks[0]).toEqual({ type: 'h2', text: '测试标题' })
  })

  test('parses h3 headings', () => {
    const blocks = parseAnalysis('### 子标题\n内容')
    expect(blocks[0]).toEqual({ type: 'h3', text: '子标题' })
  })

  test('parses unordered list items', () => {
    const blocks = parseAnalysis('- 第一项\n- 第二项')
    expect(blocks[0]).toEqual({ type: 'list', text: '- 第一项' })
    expect(blocks[1]).toEqual({ type: 'list', text: '- 第二项' })
  })

  test('parses ordered list items', () => {
    const blocks = parseAnalysis('1. 第一步\n2. 第二步')
    expect(blocks[0]).toEqual({ type: 'list', text: '1. 第一步' })
  })

  test('parses code blocks', () => {
    const blocks = parseAnalysis('```\nconst x = 1\nconsole.log(x)\n```')
    expect(blocks[0]).toEqual({ type: 'code', text: 'const x = 1\nconsole.log(x)' })
  })

  test('parses markdown tables', () => {
    const md = '| 列A | 列B |\n| --- | --- |\n| a1 | b1 |\n| a2 | b2 |'
    const blocks = parseAnalysis(md)
    expect(blocks[0]).toEqual({
      type: 'table',
      headers: ['列A', '列B'],
      rows: [['a1', 'b1'], ['a2', 'b2']],
    })
  })

  test('parses paragraphs', () => {
    const blocks = parseAnalysis('这是一段普通文本')
    expect(blocks[0]).toEqual({ type: 'p', text: '这是一段普通文本' })
  })

  test('returns empty array for empty input', () => {
    expect(parseAnalysis('')).toEqual([])
  })

  test('skips empty lines', () => {
    const blocks = parseAnalysis('## 标题\n\n\n- 项目')
    expect(blocks).toHaveLength(2)
    expect(blocks[0].type).toBe('h2')
    expect(blocks[1].type).toBe('list')
  })

  test('ignores lines that look like tables but have no separator', () => {
    const blocks = parseAnalysis('| a | b |\n内容')
    expect(blocks).toHaveLength(2)
    expect(blocks[0].type).toBe('p')
  })
})

describe('generateMarkdown', () => {
  const mockResult = {
    question: '测试问题',
    analysis: '## 分析内容\n\n这是分析结果',
    model: 'test-model',
    web_results: [
      { title: '网页1', snippet: '摘要1', url: 'https://example.com/1' },
    ],
    relevant_items: [
      {
        title: '情报项1',
        source: '来源A',
        date: '2026-05-20',
        layer: 'military',
        confidence: 0.85,
        verdict: 'verified',
        prior_class: 'medium-credibility',
        prior_probability: 0.5,
        evidence_items: [{ name: '证据1', quality: 'high', lr: 2.0, direction: 'support' }],
        bayesian_trace: [0.5, 0.67, 0.85],
        content_snippet: '这是内容片段',
      },
    ],
  }

  test('includes question and model', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('测试问题')
    expect(md).toContain('test-model')
  })

  test('includes analysis content', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('分析内容')
  })

  test('includes web results', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('网页1')
    expect(md).toContain('https://example.com/1')
  })

  test('includes relevant items with confidence', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('情报项1')
    expect(md).toContain('85%')
    expect(md).toContain('已核实')
  })

  test('includes bayesian trace', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('0.50 → 0.67 → 0.85')
  })

  test('handles empty web_results', () => {
    const md = generateMarkdown({ ...mockResult, web_results: [] })
    expect(md).not.toContain('## 网络搜索参考')
  })

  test('handles empty relevant_items', () => {
    const md = generateMarkdown({ ...mockResult, relevant_items: [] })
    expect(md).not.toContain('## 相关情报项')
  })

  test('handles missing web result title gracefully', () => {
    const md = generateMarkdown({
      ...mockResult,
      web_results: [{ title: '', snippet: 's', url: 'https://x.com' }],
    })
    expect(md).toContain('来源 1')
  })
})
