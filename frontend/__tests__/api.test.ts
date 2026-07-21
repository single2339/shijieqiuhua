import { describe, test, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { fetchCorroboration, fetchDashboard, fetchEventClusters, fetchGapAnalysis, fetchStats, fetchWarningIndicators, askQuestionIntel, generateReportIntel, superAnalyze } from '../src/api'

function mockResponse(data: unknown, ok = true, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  })
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('fetchDashboard', () => {
  test('calls /api/dashboard without params', async () => {
    mockResponse({ intel_items: [], sources: [], layers: [], total_items: 0, updated_at: '' })
    const result = await fetchDashboard()
    expect(result.total_items).toBe(0)
    expect(mockFetch).toHaveBeenCalledWith('/api/dashboard')
  })

  test('appends date params', async () => {
    mockResponse({ intel_items: [], sources: [], layers: [], total_items: 0, updated_at: '' })
    await fetchDashboard('2026-01-01', '2026-01-31')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('start_date=2026-01-01')
    expect(url).toContain('end_date=2026-01-31')
  })

  test('passes abort signal to the dashboard request', async () => {
    mockResponse({ intel_items: [], sources: [], layers: [], total_items: 0, updated_at: '' })
    const controller = new AbortController()
    await fetchDashboard(undefined, undefined, 1, 200, undefined, controller.signal)
    expect(mockFetch.mock.calls[0][1].signal).toBe(controller.signal)
  })

  test('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 })
    await expect(fetchDashboard()).rejects.toThrow('API error: 500')
  })

  test('throws on network failure', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(fetchDashboard()).rejects.toThrow('Failed to fetch')
  })
})

describe('fetchStats', () => {
  test('calls /api/stats', async () => {
    mockResponse({ total_items: 42, total_sources: 5, by_layer: [], daily_trend: [], source_matrix: [], geo_distribution: [], top_keywords: [] })
    const result = await fetchStats()
    expect(result.total_items).toBe(42)
    expect(mockFetch).toHaveBeenCalledWith('/api/stats')
  })
})

describe('fetchEventClusters', () => {
  test('calls /api/analysis/events with scoped params', async () => {
    mockResponse({ total_items: 0, total_clusters: 0, unclustered_count: 0, clusters: [] })
    await fetchEventClusters({ date: '2026-06-01', layers: ['military', 'cyber'] })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/analysis/events?')
    expect(url).toContain('date=2026-06-01')
    expect(url).toContain('layers=military%2Ccyber')
  })

  test('passes abort signal to the analysis request', async () => {
    mockResponse({ total_items: 0, total_clusters: 0, unclustered_count: 0, clusters: [] })
    const controller = new AbortController()
    await fetchEventClusters({ date: '2026-06-01' }, controller.signal)
    expect(mockFetch.mock.calls[0][1].signal).toBe(controller.signal)
  })
})

describe('fetchCorroboration', () => {
  test('calls /api/analysis/corroboration with scoped params', async () => {
    mockResponse({ sources: [], matrix: [], top_pairs: [], event_count: 0, claim_count: 0, methodology: '' })
    await fetchCorroboration({ startDate: '2026-06-01', endDate: '2026-06-02', layers: ['military'] })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/analysis/corroboration?')
    expect(url).toContain('start_date=2026-06-01')
    expect(url).toContain('end_date=2026-06-02')
    expect(url).toContain('layers=military')
  })
})

describe('fetchGapAnalysis', () => {
  test('calls /api/analysis/gaps with scoped params', async () => {
    mockResponse({ gaps: [], coverage_stats: {} })
    await fetchGapAnalysis({ startDate: '2026-06-01', endDate: '2026-06-02', layers: ['military', 'cyber'] })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/analysis/gaps?')
    expect(url).toContain('start_date=2026-06-01')
    expect(url).toContain('end_date=2026-06-02')
    expect(url).toContain('layers=military%2Ccyber')
  })
})

describe('fetchWarningIndicators', () => {
  test('calls /api/analysis/warnings with scoped params', async () => {
    mockResponse({ total_items: 0, overall_level: 'normal', active_indicator_count: 0, indicators: [], collection_requirements: [], methodology: '' })
    await fetchWarningIndicators({ date: '2026-06-01', layers: ['military', 'cyber'] })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/analysis/warnings?')
    expect(url).toContain('date=2026-06-01')
    expect(url).toContain('layers=military%2Ccyber')
  })
})

describe('askQuestionIntel', () => {
  test('posts question to /api/intel/ask', async () => {
    mockResponse({ answer: '答案', references: [], model: 'test' })
    const result = await askQuestionIntel({ question: '测试?' })
    expect(result.answer).toBe('答案')
    const [, init] = mockFetch.mock.calls[0]
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body).question).toBe('测试?')
  })

  test('throws on API error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      text: () => Promise.resolve(''),
    })
    await expect(askQuestionIntel({ question: '' })).rejects.toThrow('API error 400')
  })
})

describe('generateReportIntel', () => {
  test('posts selected brief workspace materials to /api/intel/report', async () => {
    mockResponse({ title: '简报', generated_at: '', summary: '完成', sections: [], item_count: 1, source_count: 1 })
    await generateReportIntel({
      topic: '能源态势',
      source_materials: [
        {
          id: 'item-1',
          type: 'item',
          title: '港口能源供应异常',
          summary: '多源报道显示供应链受阻',
          source: 'bbc',
          sources: ['bbc'],
          date: '2026-06-01',
          layer: 'energy',
          country: '中国',
        },
      ],
    })
    const [url, init] = mockFetch.mock.calls[0]
    const body = JSON.parse(init.body)
    expect(url).toBe('/api/intel/report')
    expect(init.method).toBe('POST')
    expect(body.source_materials).toHaveLength(1)
    expect(body.source_materials[0].type).toBe('item')
  })
})

describe('superAnalyze', () => {
  test('posts to /api/intel/super-analysis', async () => {
    mockResponse({ question: '测试', analysis: '结果', relevant_items: [], web_results: [], model: 'm' })
    await superAnalyze({ question: '测试' })
    const [url, init] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/intel/super-analysis')
    expect(init.method).toBe('POST')
  })

  test('passes signal to fetch', async () => {
    mockResponse({ question: '', analysis: '', relevant_items: [], web_results: [], model: '' })
    const controller = new AbortController()
    await superAnalyze({ question: 'x' }, controller.signal)
    expect(mockFetch.mock.calls[0][1].signal).toBe(controller.signal)
  })

  test('throws with body text on error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve('server error details'),
    })
    await expect(superAnalyze({ question: 'x' })).rejects.toThrow('API error 500: server error details')
  })

  test('throws generic message when error body is empty', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      text: () => Promise.resolve(''),
    })
    await expect(superAnalyze({ question: 'x' })).rejects.toThrow('API error 502')
  })

  test('throws on network failure', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(superAnalyze({ question: 'x' })).rejects.toThrow('Failed to fetch')
  })
})
