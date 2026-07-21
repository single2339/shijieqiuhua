import { useState, useRef, useEffect, useCallback } from 'react'
import {
  superAnalyze, fetchSuperAnalysisProgress, shouldApplySuperAnalysisProgress,
  submitSuperAnalysisReview,
} from '../api'
import type { SuperAnalysisProgress } from '../api'
import type { InvestigationPlaybook, SuperAnalysisResponse } from '../types'
import { isAbortError } from '../utils/request'

let _seq = 0

function generateRequestId(): string {
  _seq = (_seq + 1) % 9999
  return `${Date.now().toString(36)}-${_seq.toString(36)}`
}

interface UseSuperAnalysisOptions {
  startDate?: string
  endDate?: string
}

export function useSuperAnalysis({ startDate = '', endDate = '' }: UseSuperAnalysisOptions = {}) {
  const [question, setQuestion] = useState('')
  const [investigationType, setInvestigationType] = useState<InvestigationPlaybook>('general')
  const [target, setTarget] = useState('')
  const [purpose, setPurpose] = useState('')
  const [authorized, setAuthorized] = useState(false)
  const [verificationDepth, setVerificationDepth] = useState<'standard' | 'deep'>('standard')
  const [loading, setLoading] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const [result, setResult] = useState<SuperAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<SuperAnalysisProgress | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const progressControllerRef = useRef<AbortController | null>(null)
  const requestGenerationRef = useRef(0)
  const pollingRef = useRef(false)

  useEffect(() => { if (!loading) inputRef.current?.focus() }, [loading])
  useEffect(() => () => {
    requestGenerationRef.current += 1
    abortRef.current?.abort()
    progressControllerRef.current?.abort()
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
    pollingRef.current = false
  }, [])

  const handleSubmit = useCallback(async () => {
    const q = question.trim()
    if (!q || loading) return
    const targeted = investigationType !== 'general'
    const sensitive = investigationType === 'person' || investigationType === 'identity'
    if (targeted && !target.trim()) {
      setError('请选择调查目标后再开始分析')
      return
    }
    if (sensitive && (!authorized || !purpose.trim())) {
      setError('人员和身份调查需要填写合法目的并确认已获授权')
      return
    }

    const requestGeneration = ++requestGenerationRef.current
    abortRef.current?.abort()
    progressControllerRef.current?.abort()
    if (pollRef.current) clearInterval(pollRef.current)
    const controller = new AbortController()
    const progressController = new AbortController()
    abortRef.current = controller
    progressControllerRef.current = progressController

    setLoading(true)
    setError(null)
    setResult(null)
    setProgress({ phase: 'collecting', message: '启动分析引擎...', percent: 0, elapsed_seconds: 0, detail: {} })

    const requestId = generateRequestId()
    pollingRef.current = false

    pollRef.current = setInterval(async () => {
      if (pollingRef.current || progressController.signal.aborted || requestGeneration !== requestGenerationRef.current) return
      pollingRef.current = true
      try {
        const p = await fetchSuperAnalysisProgress(requestId, progressController.signal)
        if (!progressController.signal.aborted && requestGeneration === requestGenerationRef.current && shouldApplySuperAnalysisProgress(p)) setProgress(p)
      } catch (error) {
        if (!isAbortError(error) && requestGeneration === requestGenerationRef.current) {
          // Progress is best-effort; the main request remains authoritative.
        }
      }
      finally { pollingRef.current = false }
    }, 1500)

    let timeoutId: ReturnType<typeof setTimeout> | null = null
    try {
      timeoutId = setTimeout(() => controller.abort(), 300_000)
      const res = await superAnalyze({
        question: q,
        request_id: requestId,
        start_date: startDate,
        end_date: endDate,
        investigation_type: investigationType,
        target: target.trim(),
        purpose: purpose.trim(),
        authorized,
        verification_depth: verificationDepth,
      }, controller.signal)
      if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) return
      setResult(res)
    } catch (err: unknown) {
      if (requestGeneration !== requestGenerationRef.current) return
      if (isAbortError(err)) {
        if (controller.signal.aborted) {
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
      if (timeoutId) clearTimeout(timeoutId)
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      progressController.abort()
      if (progressControllerRef.current === progressController) progressControllerRef.current = null
      pollingRef.current = false
      if (abortRef.current === controller) {
        abortRef.current = null
        setLoading(false)
      }
    }
  }, [question, loading, startDate, endDate, investigationType, target, purpose, authorized, verificationDepth])

  const submitReview = useCallback(async (
    status: 'approved' | 'needs_follow_up' | 'rejected',
    notes: string,
  ) => {
    if (!result?.investigation || reviewing) return
    setReviewing(true)
    setError(null)
    try {
      const review = await submitSuperAnalysisReview(result.request_id, { status, notes: notes.trim() })
      setResult(current => current?.investigation
        ? { ...current, investigation: { ...current.investigation, analyst_review: review } }
        : current)
    } catch (err: unknown) {
      setError(err instanceof Error ? `提交复核失败：${err.message}` : '提交复核失败，请重试')
    } finally {
      setReviewing(false)
    }
  }, [result, reviewing])

  return {
    question, setQuestion, investigationType, setInvestigationType, target, setTarget,
    purpose, setPurpose, authorized, setAuthorized, verificationDepth, setVerificationDepth,
    loading, reviewing, result, error, progress,
    displayPercent: progress?.percent ?? 0,
    handleSubmit, submitReview, inputRef,
  }
}
