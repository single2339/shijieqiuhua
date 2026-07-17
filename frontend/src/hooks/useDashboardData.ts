import { useState, useCallback, useEffect, useRef } from 'react'
import type { DashboardData } from '../types'
import { fetchDashboard } from '../api'
import { isAbortError } from '../utils/request'

const PAGE_SIZE = 200
const DASHBOARD_POLL_INTERVAL_MS = 60_000


export function useDashboardData(startDate: string, endDate: string, selectedDate: string) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState('---')
  const [collecting, setCollecting] = useState(false)
  const [feedPage, setFeedPage] = useState(1)
  const [feedItems, setFeedItems] = useState<DashboardData['intel_items']>([])
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const requestGenerationRef = useRef(0)
  const loadMoreRequestGenerationRef = useRef(0)
  const requestControllerRef = useRef<AbortController | null>(null)
  const loadMoreControllerRef = useRef<AbortController | null>(null)
  const collectRequestGenerationRef = useRef(0)
  const collectControllerRef = useRef<AbortController | null>(null)
  const collectPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const hasMoreRef = useRef(hasMore)
  const loadingMoreRef = useRef(loadingMore)
  hasMoreRef.current = hasMore
  loadingMoreRef.current = loadingMore

  const loadData = useCallback(async (isPoll = false) => {
    const requestGeneration = ++requestGenerationRef.current
    requestControllerRef.current?.abort()
    loadMoreControllerRef.current?.abort()
    loadMoreRequestGenerationRef.current += 1
    setLoadingMore(false)
    const controller = new AbortController()
    requestControllerRef.current = controller
    try {
      const d = await fetchDashboard(startDate || undefined, endDate || undefined, 1, PAGE_SIZE, selectedDate, controller.signal)
      if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) return
      setData(d)
      setFeedItems(d.intel_items)
      setFeedPage(1)
      setHasMore(d.has_more)
      setLastUpdated(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
      setError(null)
    } catch (err) {
      if (isAbortError(err) || requestGeneration !== requestGenerationRef.current) return
      if (!isPoll) setError(err instanceof Error ? err.message : '情报数据加载失败')
    } finally {
      if (requestGeneration === requestGenerationRef.current) {
        setLoading(false)
        if (requestControllerRef.current === controller) requestControllerRef.current = null
      }
    }
  }, [startDate, endDate, selectedDate])

  const loadMoreItems = useCallback(async () => {
    if (!hasMoreRef.current || loadingMoreRef.current || requestControllerRef.current) return
    const requestGeneration = ++loadMoreRequestGenerationRef.current
    loadMoreControllerRef.current?.abort()
    const controller = new AbortController()
    loadMoreControllerRef.current = controller
    setLoadingMore(true)
    try {
      const nextPage = feedPage + 1
      const d = await fetchDashboard(startDate || undefined, endDate || undefined, nextPage, PAGE_SIZE, selectedDate, controller.signal)
      if (controller.signal.aborted || requestGeneration !== loadMoreRequestGenerationRef.current) return
      setFeedItems(prev => [...prev, ...d.intel_items])
      setFeedPage(d.page || nextPage)
      setHasMore(d.has_more)
      setData(prev => prev ? { ...prev, page: d.page || nextPage, page_size: d.page_size, has_more: d.has_more } : prev)
    } catch (err) {
      if (isAbortError(err) || requestGeneration !== loadMoreRequestGenerationRef.current) return
      setError(err instanceof Error ? err.message : '加载更多失败')
    } finally {
      if (requestGeneration === loadMoreRequestGenerationRef.current) {
        setLoadingMore(false)
        if (loadMoreControllerRef.current === controller) loadMoreControllerRef.current = null
      }
    }
  }, [feedPage, startDate, endDate, selectedDate])

  const loadDataRef = useRef(loadData)
  loadDataRef.current = loadData

  useEffect(() => {
    loadData()
    const id = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      void loadData(true)
    }, DASHBOARD_POLL_INTERVAL_MS)
    return () => {
      clearInterval(id)
      requestControllerRef.current?.abort()
      loadMoreControllerRef.current?.abort()
      requestGenerationRef.current += 1
      loadMoreRequestGenerationRef.current += 1
    }
  }, [loadData])

  const triggerCollect = useCallback(async () => {
    const requestGeneration = ++collectRequestGenerationRef.current
    collectControllerRef.current?.abort()
    if (collectPollRef.current) {
      clearInterval(collectPollRef.current)
      collectPollRef.current = null
    }
    const controller = new AbortController()
    collectControllerRef.current = controller
    setCollecting(true)
    setError(null)
    try {
      const res = await fetch('/api/collect', { method: 'POST', signal: controller.signal })
      const result = await res.json()
      if (controller.signal.aborted || requestGeneration !== collectRequestGenerationRef.current) return
      if (result.status === 'started' || result.status === 'running') {
        const poll = setInterval(async () => {
          if (controller.signal.aborted || requestGeneration !== collectRequestGenerationRef.current) {
            clearInterval(poll)
            if (collectPollRef.current === poll) collectPollRef.current = null
            return
          }
          try {
            const sr = await fetch('/api/collect/status', { signal: controller.signal })
            const st = await sr.json()
            if (controller.signal.aborted || requestGeneration !== collectRequestGenerationRef.current) return
            if (st.status === 'completed') {
              clearInterval(poll)
              if (collectPollRef.current === poll) collectPollRef.current = null
              await loadDataRef.current()
              if (controller.signal.aborted || requestGeneration !== collectRequestGenerationRef.current) return
              if (collectControllerRef.current === controller) collectControllerRef.current = null
              setCollecting(false)
            } else if (st.status === 'error') {
              clearInterval(poll)
              if (collectPollRef.current === poll) collectPollRef.current = null
              if (collectControllerRef.current === controller) collectControllerRef.current = null
              setError(st.message || '采集失败')
              setCollecting(false)
            }
          } catch (err) {
            if (isAbortError(err) || requestGeneration !== collectRequestGenerationRef.current) return
            clearInterval(poll)
            if (collectPollRef.current === poll) collectPollRef.current = null
            if (collectControllerRef.current === controller) collectControllerRef.current = null
            setError('采集状态检查失败')
            setCollecting(false)
          }
        }, 3000)
        collectPollRef.current = poll
      } else {
        setCollecting(false)
      }
    } catch (err) {
      if (isAbortError(err) || requestGeneration !== collectRequestGenerationRef.current) return
      setError(err instanceof Error ? err.message : '采集请求失败')
      setCollecting(false)
    } finally {
      if (requestGeneration === collectRequestGenerationRef.current && collectControllerRef.current === controller && !collectPollRef.current) {
        collectControllerRef.current = null
      }
    }
  }, [])

  useEffect(() => () => {
    collectRequestGenerationRef.current += 1
    collectControllerRef.current?.abort()
    if (collectPollRef.current) clearInterval(collectPollRef.current)
  }, [])

  return {
    data, loading, error, lastUpdated, collecting, hasMore,
    feedPage, feedItems, loadingMore,
    loadData, loadMoreItems, triggerCollect,
  }
}
