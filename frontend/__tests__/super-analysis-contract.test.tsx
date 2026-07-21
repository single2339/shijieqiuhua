import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

import * as api from '../src/api'
import SuperAnalysisPanel from '../src/components/SuperAnalysisPanel'
import { generateHTML, generateMarkdown } from '../src/lib/markdown'
import type { SuperAnalysisResponse } from '../src/types'

const result: SuperAnalysisResponse = {
  question: '测试问题',
  analysis: '分析结果',
  relevant_items: [
    {
      title: '聚焦情报',
      source: 'Reuters',
      date: '2026-07-16',
      layer: 'politics',
      quality_score: 0.82,
      independent_source_count: 1,
      source_class: 'high-credibility',
      content_snippet: '摘要',
    },
  ],
  web_results: [{ title: '网页线索', snippet: '搜索摘要', url: 'https://example.com/report' }],
  hypothesis_assessment: {
    hypothesis: '港口吞吐量上升',
    prior_probability: 0.5,
    posterior_probability: 0.6,
    verdict: 'uncertain',
    confidence_level: 'L3',
    independent_source_count: 1,
    evidence: [{
      evidence_id: 'I1',
      source: 'Reuters',
      relation: 'support',
      strength: 'weak',
      likelihood_ratio: 1.5,
      posterior_probability: 0.6,
      rationale: '有限支持',
    }],
  },
  investigation: {
    playbook: 'event',
    scope: { target: '示例港口事件' },
    plan: { playbook: 'event', target: '示例港口事件', collection_steps: ['检索内部情报'], verification_steps: ['交叉验证'] },
    evidence: [{
      id: 'LI1', kind: 'internal_intelligence', title: '港口延误通报', source: 'Reuters',
      provenance: 'bronze://doc-1', collected_at: '2026-07-20T00:00:00Z', verification_status: 'collected',
      summary: '港口出现延误', source_url: 'https://example.com/original', content_sha256: '', data: {},
    }],
    relationship_graph: {
      nodes: [{ id: 'target:港口', label: '示例港口事件', type: 'target' }],
      edges: [{ source: 'evidence:LI1', target: 'target:港口', relation: 'reports_on', evidence_ids: ['LI1'] }],
    },
    timeline: [{ date: '2026-07-20', evidence_ids: ['LI1'], summary: '一条记录' }],
    pending_verification: [{ id: 'PV1', question: '核验原始来源', priority: 'high', related_evidence_ids: ['LI1'] }],
    alternative_explanations: [{ id: 'ALT1', explanation: '可能来自同一首发材料', indicators: [] }],
    recommended_next_steps: [{ priority: 'high', task: '取得原始来源', rationale: '确认来源链', query: '示例港口事件' }],
    analyst_review: { status: 'pending', reviewer_id: null, reviewed_at: '', notes: '' },
    errors: [],
  },
  collection_status: 'partial',
  provider_statuses: { bing_cn: 'error', duckduckgo: 'success' },
  degraded: true,
  analysis_status: 'complete',
  errors: ['bing_cn_unavailable'],
  model: 'real-provider/model-v1',
  request_id: 'request-1234',
}

vi.mock('../src/hooks/useSuperAnalysis', () => ({
  useSuperAnalysis: () => ({
    question: '',
    setQuestion: vi.fn(),
    loading: false,
    result,
    error: null,
    progress: null,
    displayPercent: 0,
    handleSubmit: vi.fn(),
    inputRef: { current: null },
  }),
}))

vi.mock('../src/hooks/useFloatingPanel', () => ({
  useFloatingPanel: () => ({ panelStyle: {}, dragHandleProps: {}, dragHandleStyle: {} }),
}))

describe('super analysis response contract', () => {
  test('renders hypothesis confidence, source independence, and document quality without document confidence', () => {
    const html = renderToStaticMarkup(React.createElement(SuperAnalysisPanel, { onClose: vi.fn() }))

    expect(html).toContain('结构化假设评估')
    expect(html).toContain('L3')
    expect(html).toContain('后验 60%')
    expect(html).toContain('support/weak')
    expect(html).toContain('聚合独立来源 1')
    expect(html).toContain('文档质量 82%')
    expect(html).toContain('调查证据与复核')
    expect(html).toContain('批准结论')
    expect(html).toContain('需要补证')
    expect(html).toContain('驳回结论')
  })

  test('renders degraded collection and analysis status with errors', () => {
    const html = renderToStaticMarkup(React.createElement(SuperAnalysisPanel, { onClose: vi.fn() }))

    expect(html).toContain('降级分析')
    expect(html).toContain('采集状态：partial')
    expect(html).toContain('分析状态：complete')
    expect(html).toContain('bing_cn_unavailable')
    expect(html).toContain('未验证')
  })

  test('renders a successful empty collection without a degradation warning', () => {
    const original = { ...result }
    Object.assign(result, {
      collection_status: 'empty',
      provider_statuses: { internal: 'empty', bing_cn: 'empty', duckduckgo: 'empty' },
      degraded: false,
      analysis_status: 'unavailable',
      errors: [],
      hypothesis_assessment: null,
    })

    try {
      const html = renderToStaticMarkup(React.createElement(SuperAnalysisPanel, { onClose: vi.fn() }))
      expect(html).toContain('未找到相关情报')
      expect(html).toContain('数据源均已正常查询')
      expect(html).not.toContain('降级分析')
    } finally {
      Object.assign(result, original)
    }
  })

  test('exports the structured hypothesis trace and degraded status', () => {
    const markdown = generateMarkdown(result)
    const html = generateHTML(result)

    for (const output of [markdown, html]) {
      expect(output).toContain('结构化假设评估')
      expect(output).toContain('L3')
      expect(output).toContain('60%')
      expect(output).toContain('support')
      expect(output).toContain('1.5')
      expect(output).toContain('聚合独立来源')
      expect(output).toContain('文档质量')
      expect(output).toContain('high-credibility')
      expect(output).toContain('partial')
      expect(output).toContain('bing_cn_unavailable')
      expect(output).not.toContain('先验类别')
      expect(output).not.toContain('置信度追踪')
    }
  })

  test('uses the same client request ID for analysis and progress polling', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => result })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ phase: 'collecting', message: 'working', percent: 5, elapsed_seconds: 1, detail: {} }),
      })
    vi.stubGlobal('fetch', fetchMock)

    try {
      await api.superAnalyze({ question: '测试问题', request_id: 'request-1234' })
      await api.fetchSuperAnalysisProgress('request-1234')

      expect(JSON.parse(fetchMock.mock.calls[0][1].body).request_id).toBe('request-1234')
      expect(fetchMock.mock.calls[1][0]).toBe('/api/super-analysis/progress?request_id=request-1234')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  test('submits an owner-scoped analyst review for the request', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'approved', reviewer_id: 7, reviewed_at: '2026-07-21T00:00:00Z', notes: '已核验' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    try {
      const review = await api.submitSuperAnalysisReview('request-1234', { status: 'approved', notes: '已核验' })

      expect(review.status).toBe('approved')
      expect(fetchMock.mock.calls[0][0]).toBe('/api/intel/super-analysis/request-1234/review')
      expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ status: 'approved', notes: '已核验' })
    } finally {
      vi.unstubAllGlobals()
    }
  })

  test('treats a 404 progress lookup as unavailable instead of a state update', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
    vi.stubGlobal('fetch', fetchMock)

    try {
      await expect(api.fetchSuperAnalysisProgress('request-1234')).rejects.toThrow('Progress API error: 404')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  test('rejects idle progress updates so they cannot replace the startup state', () => {
    const shouldApply = Reflect.get(api, 'shouldApplySuperAnalysisProgress')

    expect(shouldApply).toBeTypeOf('function')
    if (typeof shouldApply !== 'function') return
    expect(shouldApply({ phase: 'idle', message: 'idle', percent: 0, elapsed_seconds: 0, detail: {} })).toBe(false)
    expect(shouldApply({ phase: 'collecting', message: 'working', percent: 5, elapsed_seconds: 1, detail: {} })).toBe(true)
  })
})
