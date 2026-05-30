import { useState, useCallback, useEffect, useRef } from 'react'
import type { DashboardData } from '../types'
import { fetchDashboard } from '../api'

const PAGE_SIZE = 200

export function useDashboardData(startDate: string, endDate: string, selectedDate: string) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState('---')
  const [collecting, setCollecting] = useState(false)
  const [feedPage, setFeedPage] = useState(1)
  const [feedItems, setFeedItems] = useState<DashboardData['intel_items']>([])
  const [loadingMore, setLoadingMore] = useState(false)
  const hasMoreRef = useRef(data?.has_more ?? false)
  const loadingMoreRef = useRef(loadingMore)
  hasMoreRef.current = data?.has_more ?? false
  loadingMoreRef.current = loadingMore

  const loadData = useCallback(async (isPoll = false) => {
    try {
      const d = await fetchDashboard(startDate || undefined, endDate || undefined, 1, PAGE_SIZE, selectedDate)
      setData(d)
      if (!isPoll) {
        setFeedItems(d.intel_items)
        setFeedPage(1)
      }
      setLastUpdated(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
      setError(null)
    } catch (err) {
      if (!isPoll) setError(err instanceof Error ? err.message : '情报数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [startDate, endDate, selectedDate])

  const loadMoreItems = useCallback(async () => {
    if (!hasMoreRef.current || loadingMoreRef.current) return
    setLoadingMore(true)
    try {
      const nextPage = feedPage + 1
      const d = await fetchDashboard(startDate || undefined, endDate || undefined, nextPage, PAGE_SIZE, selectedDate)
      setFeedItems(prev => [...prev, ...d.intel_items])
      setFeedPage(nextPage)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载更多失败')
    } finally {
      setLoadingMore(false)
    }
  }, [feedPage, startDate, endDate, selectedDate])

  useEffect(() => {
    loadData()
    const id = setInterval(() => loadData(true), 10_000)
    return () => clearInterval(id)
  }, [loadData])

  const triggerCollect = useCallback(async () => {
    setCollecting(true)
    setError(null)
    try {
      const res = await fetch('/api/collect', { method: 'POST' })
      const result = await res.json()
      if (result.status === 'started' || result.status === 'running') {
        const poll = setInterval(async () => {
          try {
            const sr = await fetch('/api/collect/status')
            const st = await sr.json()
            if (st.status === 'completed') {
              clearInterval(poll)
              await loadData()
              setCollecting(false)
            } else if (st.status === 'error') {
              clearInterval(poll)
              setError(st.message || '采集失败')
              setCollecting(false)
            }
          } catch { clearInterval(poll); setError('采集状态检查失败'); setCollecting(false) }
        }, 3000)
      } else {
        setCollecting(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '采集请求失败')
      setCollecting(false)
    }
  }, [loadData])

  return {
    data, loading, error, lastUpdated, collecting,
    feedPage, feedItems, loadingMore,
    loadData, loadMoreItems, triggerCollect,
  }
}
