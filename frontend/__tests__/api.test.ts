import { describe, test, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { fetchDashboard, fetchStats, askQuestion, superAnalyze } from '../src/api'

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

describe('askQuestion', () => {
  test('posts question to /api/ask', async () => {
    mockResponse({ answer: '答案', references: [], model: 'test' })
    const result = await askQuestion({ question: '测试?' })
    expect(result.answer).toBe('答案')
    const [, init] = mockFetch.mock.calls[0]
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body).question).toBe('测试?')
  })

  test('throws on API error', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 400 })
    await expect(askQuestion({ question: '' })).rejects.toThrow('API error: 400')
  })
})

describe('superAnalyze', () => {
  test('posts to /api/super-analysis', async () => {
    mockResponse({ question: '测试', analysis: '结果', relevant_items: [], web_results: [], model: 'm' })
    await superAnalyze({ question: '测试' })
    const [url, init] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/super-analysis')
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
