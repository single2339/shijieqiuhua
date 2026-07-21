import { describe, test, expect } from 'vitest'
import { parseAnalysis, generateMarkdown, generateHTML } from '../src/lib/markdown'
import type { SuperAnalysisResponse } from '../src/types'

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
    hypothesis_assessment: null,
    collection_status: 'complete',
    provider_statuses: {},
    degraded: false,
    analysis_status: 'complete',
    errors: [],
    request_id: 'request-1234',
    web_results: [
      { title: '网页1', snippet: '摘要1', url: 'https://example.com/1' },
    ],
    relevant_items: [
      {
        title: '情报项1',
        source: '来源A',
        date: '2026-05-20',
        layer: 'military',
        quality_score: 0.85,
        independent_source_count: 2,
        source_class: 'medium-credibility',
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

  test('includes relevant items with document quality and aggregated sources', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('情报项1')
    expect(md).toContain('聚合独立来源: 2')
    expect(md).toContain('文档质量: 85%')
    expect(md).toContain('medium-credibility')
  })

  test('labels web search snippets as unverified', () => {
    const md = generateMarkdown(mockResult)
    expect(md).toContain('网络搜索摘要（未验证）')
  })

  test('handles empty web_results', () => {
    const md = generateMarkdown({ ...mockResult, web_results: [] })
    expect(md).not.toContain('## 网络搜索摘要（未验证）')
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

describe('generateHTML', () => {
  const mockResult = {
    question: '测试 <问题>',
    analysis: '## 分析内容\n\n这是 **重点 <内容>**。\n\n- 待核查 <script>alert(1)</script>',
    model: 'test-model',
    hypothesis_assessment: null,
    collection_status: 'complete',
    provider_statuses: {},
    degraded: false,
    analysis_status: 'complete',
    errors: [],
    request_id: 'request-1234',
    web_results: [
      { title: '网页 <1>', snippet: '摘要 <script>alert(2)</script>', url: 'https://example.com/?q=<x>' },
    ],
    relevant_items: [
      {
        title: '情报项 <1>',
        source: '来源 <A>',
        date: '2026-05-20',
        layer: 'military',
        quality_score: 0.85,
        independent_source_count: 2,
        source_class: 'medium-credibility',
        content_snippet: '这是内容 <片段>',
      },
    ],
  }

  test('returns a complete HTML document', () => {
    const html = generateHTML(mockResult)

    expect(html.trim().toLowerCase().startsWith('<!doctype html>')).toBe(true)
    expect(html).toContain('<html lang="zh-CN">')
    expect(html).toContain('<head>')
    expect(html).toContain('<meta charset="UTF-8">')
    expect(html).toContain('<title>超级分析报告')
    expect(html).toContain('<style>')
    expect(html).toContain('<body>')
    expect(html).toContain('</html>')
  })

  test('escapes user content while preserving bold markup', () => {
    const html = generateHTML(mockResult)

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('&lt;问题&gt;')
    expect(html).toContain('<strong style="color:#0d9488;font-weight:700;">重点 &lt;内容&gt;</strong>')
  })

  test('renders non-http(s) web result URLs without an anchor', () => {
    const html = generateHTML({
      ...mockResult,
      web_results: [
        { title: '恶意链接', snippet: 'x', url: 'javascript:alert(1)' },
        { title: '正常链接', snippet: 'y', url: 'https://example.com/a' },
      ],
    })

    expect(html).not.toContain('href="javascript:')
    expect(html).not.toContain('href=""')
    expect(html).toContain('恶意链接')
    expect(html).toContain('href="https://example.com/a"')
  })

  test('renders safe Markdown links and leaves unsafe links as plain text', () => {
    const html = generateHTML({
      ...mockResult,
      analysis: '查看 [原始来源](https://example.com/source) 并忽略 [危险链接](javascript:alert(1))。',
    })

    expect(html).toContain('href="https://example.com/source"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).not.toContain('[原始来源](https://example.com/source)')
    expect(html).not.toContain('href=""')
    expect(html).not.toContain('href="javascript:')
    expect(html).toContain('危险链接')
  })

  test('exports the complete investigation trace and source links', () => {
    const result: SuperAnalysisResponse = {
      ...mockResult,
      relevant_items: [{
        ...mockResult.relevant_items[0],
        document_id: 'DOC-001',
        source_url: 'https://example.com/intel/DOC-001',
      }],
      investigation: {
        playbook: 'event',
        scope: { target: '示例港口事件' },
        plan: {
          playbook: 'event',
          target: '示例港口事件',
          collection_steps: ['检索港口公告'],
          verification_steps: ['交叉核验船期'],
        },
        evidence: [{
          id: 'EV-001',
          kind: '内部情报',
          title: '港口延误通报',
          source: 'Reuters',
          provenance: 'bronze://doc-1',
          collected_at: '2026-07-20T00:00:00Z',
          verification_status: 'corroborated',
          summary: '港口平均等待时间增加两天',
          source_url: 'https://example.com/evidence/EV-001',
          content_sha256: 'abc123',
          data: {},
        }],
        relationship_graph: {
          nodes: [{ id: 'target:port', label: '示例港口', type: 'target' }],
          edges: [{ source: 'evidence:EV-001', target: 'target:port', relation: 'reports_on', evidence_ids: ['EV-001'] }],
        },
        timeline: [{ date: '2026-07-20', evidence_ids: ['EV-001'], summary: '发布延误通报' }],
        pending_verification: [{
          id: 'PV-001',
          question: '等待时间是否持续增加',
          priority: 'high',
          rationale: '需要确认趋势而非单点异常',
          related_evidence_ids: ['EV-001'],
        }],
        alternative_explanations: [{
          id: 'ALT-001',
          explanation: '恶劣天气导致短期拥堵',
          indicators: ['当地气象警报'],
          related_evidence_ids: ['EV-001'],
          confidence_level: 'L2',
        }],
        recommended_next_steps: [{
          priority: 'high',
          task: '获取最新船期',
          rationale: '确认延误持续性',
          query: '示例港口 最新船期',
        }],
        analyst_review: { status: 'pending', reviewer_id: null, reviewed_at: '', notes: '' },
        errors: [],
      },
    }

    const html = generateHTML(result)

    for (const expected of [
      '检索港口公告',
      '交叉核验船期',
      'Reuters',
      '港口平均等待时间增加两天',
      'abc123',
      'EV-001',
      '当地气象警报',
      'L2',
      '需要确认趋势而非单点异常',
      '示例港口 最新船期',
      'DOC-001',
    ]) {
      expect(html).toContain(expected)
    }
    expect(html).toContain('href="https://example.com/evidence/EV-001"')
    expect(html).toContain('href="https://example.com/intel/DOC-001"')
  })
})
