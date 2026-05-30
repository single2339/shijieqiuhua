import { useState } from 'react'
import { Sparkle } from '@phosphor-icons/react'
import type { AnalysisInterpretRequest } from '../../types'
import { interpretAnalysis } from '../../api'

interface Props {
  analysisType: string
  context: Record<string, unknown>
  label?: string
}

export default function AIInterpretBadge({ analysisType, context, label = 'AI 解读' }: Props) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  const handleInterpret = async () => {
    setLoading(true)
    setError('')
    setResult('')
    try {
      const req: AnalysisInterpretRequest = { analysis_type: analysisType, context }
      const res = await interpretAnalysis(req)
      setResult(res.interpretation)
    } catch {
      setError('AI 解读请求失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      {!result && (
        <button
          onClick={handleInterpret}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 18px',
            background: loading ? 'rgba(147,51,234,0.1)' : 'rgba(147,51,234,0.2)',
            border: '1px solid rgba(147,51,234,0.4)',
            borderRadius: 12,
            color: loading ? '#a78bfa' : '#c084fc',
            fontSize: 14,
            fontWeight: 500,
            cursor: loading ? 'wait' : 'pointer',
          }}
        >
          <Sparkle size={16} weight="fill" />
          {loading ? '分析中...' : label}
        </button>
      )}

      {error && (
        <div style={{ color: '#f87171', fontSize: 13, marginTop: 10 }}>
          {error}
          <button
            onClick={handleInterpret}
            style={{ color: '#c084fc', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, marginLeft: 8 }}
          >
            重试
          </button>
        </div>
      )}

      {result && (
        <div
          style={{
            marginTop: 16,
            padding: 16,
            background: 'rgba(147,51,234,0.08)',
            border: '1px solid rgba(147,51,234,0.2)',
            borderRadius: 12,
            fontSize: 14,
            lineHeight: 1.8,
            color: '#e2e8f0',
            whiteSpace: 'pre-wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, color: '#a78bfa', fontSize: 12, fontWeight: 600 }}>
            <Sparkle size={14} weight="fill" />
            AI 解读
          </div>
          {result}
        </div>
      )}
    </div>
  )
}
