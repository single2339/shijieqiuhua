import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Warning, WarningCircle } from '@phosphor-icons/react'
import type { AnomalyResult } from '../../types'
import { LAYER_META } from '../../types'
import { fetchAnomalies } from '../../api'
import AIInterpretBadge from './AIInterpretBadge'

interface Props {
  startDate?: string
  endDate?: string
}

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  critical: { color: '#f87171', bg: 'rgba(248,113,113,0.1)', label: '严重' },
  high: { color: '#fb923c', bg: 'rgba(251,146,60,0.1)', label: '高' },
  medium: { color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', label: '中' },
  low: { color: '#a3a3a3', bg: 'rgba(163,163,163,0.06)', label: '低' },
}

export default function AnomalyView({ startDate, endDate }: Props) {
  const [data, setData] = useState<AnomalyResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<'date' | 'severity' | 'z_score'>('z_score')

  useEffect(() => {
    setLoading(true)
    fetchAnomalies(startDate, endDate)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [startDate, endDate])

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          style={{
            width: 20, height: 20, borderRadius: '50%', margin: '0 auto',
            border: '2px solid var(--border-subtle)', borderTopColor: 'var(--accent)',
          }}
        />
      </div>
    )
  }

  if (error) {
    return <div style={{ color: 'var(--danger)', fontSize: 11, textAlign: 'center', padding: 20 }}>{error}</div>
  }

  const anomalies = data?.anomalies ?? []
  const sorted = [...anomalies].sort((a, b) => {
    if (sortKey === 'severity') {
      const sev: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 }
      return (sev[b.severity] ?? 0) - (sev[a.severity] ?? 0)
    }
    if (sortKey === 'z_score') return Math.abs(b.z_score) - Math.abs(a.z_score)
    return a.date.localeCompare(b.date)
  })

  return (
    <div>
      {/* Sort controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>排序:</span>
        {[
          { key: 'z_score' as const, label: 'Z值' },
          { key: 'severity' as const, label: '严重度' },
          { key: 'date' as const, label: '日期' },
        ].map(s => (
          <button
            key={s.key}
            onClick={() => setSortKey(s.key)}
            style={{
              background: sortKey === s.key ? 'rgba(16,185,129,0.1)' : 'var(--bg-deep)',
              border: sortKey === s.key ? '1px solid rgba(16,185,129,0.25)' : '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-sm)', color: sortKey === s.key ? 'var(--accent)' : 'var(--text-tertiary)',
              padding: '2px 8px', cursor: 'pointer', fontSize: 9, fontFamily: 'var(--font-mono)',
            }}
          >
            {s.label}
          </button>
        ))}
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>
          共 {anomalies.length} 个异常
        </span>
      </div>

      {sorted.length === 0 && (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>
          未检测到异常事件
        </div>
      )}

      {/* Anomaly cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
        {sorted.map((a, i) => {
          const sev = SEVERITY_CONFIG[a.severity] ?? SEVERITY_CONFIG.low
          const meta = LAYER_META[a.layer as keyof typeof LAYER_META]
          return (
            <motion.div
              key={`${a.date}-${a.layer}-${i}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.02 }}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px',
                background: sev.bg,
                border: `1px solid ${sev.color}22`,
                borderRadius: 'var(--radius-md)',
              }}
            >
              {a.severity === 'critical' || a.severity === 'high'
                ? <Warning size={16} weight="fill" color={sev.color} />
                : <WarningCircle size={14} weight="duotone" color={sev.color} />
              }
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-primary)' }}>{a.date}</span>
                  {meta && (
                    <span style={{ fontSize: 9, color: meta.color, fontFamily: 'var(--font-mono)' }}>
                      {meta.label}
                    </span>
                  )}
                  {a.country && (
                    <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{a.country}</span>
                  )}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                  实际 {a.actual_count} / 预期 {a.expected_count} · Z = {a.z_score >= 0 ? '+' : ''}{a.z_score}
                </div>
              </div>
              <span style={{
                fontSize: 9, fontWeight: 700, padding: '2px 8px',
                borderRadius: 99, background: `${sev.color}22`, color: sev.color,
                fontFamily: 'var(--font-mono)',
              }}>
                {sev.label}
              </span>
            </motion.div>
          )
        })}
      </div>

      {/* Baseline summary */}
      {data?.baseline && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>
            基线统计
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {Object.entries(data.baseline).map(([layer, bl]) => {
              const meta = LAYER_META[layer as keyof typeof LAYER_META]
              return (
                <span key={layer} style={{
                  fontSize: 9, color: meta?.color ?? 'var(--text-tertiary)',
                  fontFamily: 'var(--font-mono)', padding: '2px 6px',
                  background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
                }}>
                  {meta?.label ?? layer}: μ={bl.mean} σ={bl.std}
                </span>
              )
            })}
          </div>
        </div>
      )}

      <AIInterpretBadge
        analysisType="anomaly"
        context={{ anomaly_count: anomalies.length, critical_count: anomalies.filter(a => a.severity === 'critical').length }}
      />
    </div>
  )
}
