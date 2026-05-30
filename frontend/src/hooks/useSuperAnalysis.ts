import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { superAnalyze, fetchSuperAnalysisProgress } from '../api'
import type { SuperAnalysisProgress } from '../api'
import type { SuperAnalysisResponse } from '../types'

export function useSuperAnalysis() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SuperAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<SuperAnalysisProgress | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => { if (!loading) inputRef.current?.focus() }, [loading])
  useEffect(() => () => abortRef.current?.abort(), [])

  const handleSubmit = useCallback(async () => {
    const q = question.trim()
    if (!q || loading) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setResult(null)
    setProgress({ phase: 'collecting', message: '启动分析引擎...', percent: 0, elapsed_seconds: 0, detail: {} })

    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const p = await fetchSuperAnalysisProgress()
        setProgress(p)
      } catch { /* ignore polling errors */ }
    }, 1500)

    try {
      const timeoutId = setTimeout(() => controller.abort(), 300_000)
      const res = await superAnalyze({ question: q }, controller.signal)
      clearTimeout(timeoutId)
      setResult(res)
      abortRef.current = null
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (controller.signal.aborted && abortRef.current === controller) {
          setError('分析请求超时（5分钟），请简化问题后重试')
        }
      } else if (err instanceof TypeError) {
        setError('网络连接失败，请检查网络后重试')
      } else if (err instanceof Error) {
        setError(err.message.startsWith('API error')
          ? `服务端错误：${err.message}`
          : `请求失败：${err.message}`)
      } else {
        setError('分析请求失败，请重试')
      }
    } finally {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      if (abortRef.current === controller) abortRef.current = null
      setLoading(false)
    }
  }, [question, loading])

  const tick = useRef(0)
  useEffect(() => {
    if (progress?.phase !== 'analyzing') { tick.current = 0; return }
    const interval = setInterval(() => { tick.current++ }, 2000)
    return () => clearInterval(interval)
  }, [progress?.phase])

  const displayPercent = useMemo(() => {
    if (!progress) return 0
    if (progress.phase === 'done' || progress.phase === 'error') return progress.percent
    if (progress.phase === 'analyzing') {
      const crept = Math.min(tick.current * 0.5, 57)
      return Math.round(progress.percent + crept)
    }
    return progress.percent
  }, [progress, tick.current])

  return {
    question, setQuestion, loading, result, error, progress, displayPercent,
    handleSubmit, inputRef,
  }
}
