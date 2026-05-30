import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import type { RiskHeatmapResult, RegionRisk } from '../../types'
import { fetchRiskHeatmap } from '../../api'
import AIInterpretBadge from './AIInterpretBadge'

function riskColor(score: number): string {
  if (score >= 0.7) return '#f87171'
  if (score >= 0.5) return '#fb923c'
  if (score >= 0.3) return '#fbbf24'
  return '#34d399'
}

function riskBg(score: number): string {
  if (score >= 0.7) return 'rgba(248,113,113,0.1)'
  if (score >= 0.5) return 'rgba(251,146,60,0.08)'
  if (score >= 0.3) return 'rgba(251,191,36,0.06)'
  return 'rgba(52,211,153,0.05)'
}

export default function RiskHeatmapView() {
  const [data, setData] = useState<RiskHeatmapResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<keyof RegionRisk>('risk_score')

  useEffect(() => {
    fetchRiskHeatmap()
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [])

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

  const regions = data?.regions ?? []
  if (regions.length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>暂无风险数据</div>
  }

  const sorted = [...regions].sort((a, b) => (b[sortKey] as number) - (a[sortKey] as number))
  const maxRisk = Math.max(...regions.map(r => r.risk_score), 0.01)

  return (
    <div>
      {/* Sort controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>排序:</span>
        {[
          { key: 'risk_score' as const, label: '风险评分' },
          { key: 'intel_density' as const, label: '情报密度' },
          { key: 'avg_confidence' as const, label: '平均置信度' },
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
      </div>

      {/* Horizontal bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginBottom: 16 }}>
        {sorted.slice(0, 20).map((r, i) => (
          <motion.div
            key={r.country}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.02 }}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 10px', borderRadius: 'var(--radius-sm)',
              background: riskBg(r.risk_score),
            }}
          >
            <span style={{ fontSize: 10, color: 'var(--text-primary)', minWidth: 70, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {r.country}
            </span>
            <div style={{ flex: 1, height: 10, background: 'var(--bg-deep)', borderRadius: 5, overflow: 'hidden' }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(r.risk_score / maxRisk) * 100}%` }}
                transition={{ delay: i * 0.02, duration: 0.4, ease: 'easeOut' }}
                style={{ height: '100%', background: riskColor(r.risk_score), borderRadius: 5, opacity: 0.7 }}
              />
            </div>
            <span style={{
              fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
              color: riskColor(r.risk_score), minWidth: 36, textAlign: 'right',
            }}>
              {(r.risk_score * 100).toFixed(0)}
            </span>
          </motion.div>
        ))}
      </div>

      {/* Detail table */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
          区域详情 (TOP 15)
        </div>
        <div style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9 }}>
            <thead>
              <tr style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                <th style={{ textAlign: 'left', padding: '2px 6px' }}>国家</th>
                <th style={{ textAlign: 'right', padding: '2px 6px' }}>风险</th>
                <th style={{ textAlign: 'right', padding: '2px 6px' }}>密度</th>
                <th style={{ textAlign: 'right', padding: '2px 6px' }}>置信度</th>
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 15).map(r => (
                <tr key={r.country} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '3px 6px', color: 'var(--text-primary)' }}>{r.country}</td>
                  <td style={{ padding: '3px 6px', textAlign: 'right', color: riskColor(r.risk_score), fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {(r.risk_score * 100).toFixed(0)}
                  </td>
                  <td style={{ padding: '3px 6px', textAlign: 'right', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {r.intel_density}
                  </td>
                  <td style={{ padding: '3px 6px', textAlign: 'right', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {(r.avg_confidence * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <AIInterpretBadge
        analysisType="risk_heatmap"
        context={{ region_count: regions.length, top_regions: sorted.slice(0, 5).map(r => r.country) }}
      />
    </div>
  )
}
