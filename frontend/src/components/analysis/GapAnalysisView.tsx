import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Warning, WarningCircle, Globe, Clock, LinkBreak, Hash } from '@phosphor-icons/react'
import type { GapAnalysisResult } from '../../types'
import { fetchGapAnalysis } from '../../api'
import AIInterpretBadge from './AIInterpretBadge'

const GAP_ICONS: Record<string, typeof Warning> = {
  region: Globe,
  topic: Hash,
  time: Clock,
  cross_source: LinkBreak,
}

const GAP_LABELS: Record<string, string> = {
  region: '区域覆盖',
  topic: '主题覆盖',
  time: '时间连续性',
  cross_source: '信源多样性',
}

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  critical: { color: '#f87171', bg: 'rgba(248,113,113,0.1)', label: '严重' },
  high: { color: '#fb923c', bg: 'rgba(251,146,60,0.1)', label: '高' },
  medium: { color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', label: '中' },
  low: { color: '#a3a3a3', bg: 'rgba(163,163,163,0.06)', label: '低' },
}

export default function GapAnalysisView() {
  const [data, setData] = useState<GapAnalysisResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchGapAnalysis()
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

  const gaps = data?.gaps ?? []
  const stats = data?.coverage_stats ?? {}

  return (
    <div>
      {/* Coverage stats */}
      {Object.keys(stats).length > 0 && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8,
          marginBottom: 14,
        }}>
          {[
            { key: 'total_items', label: '情报总量', fmt: (v: number) => v },
            { key: 'countries_covered', label: '覆盖国家', fmt: (v: number) => v },
            { key: 'layers_covered', label: '活跃图层', fmt: (v: number) => `${v}/12` },
            { key: 'time_coverage', label: '时间覆盖率', fmt: (v: number) => `${(v * 100).toFixed(0)}%` },
            { key: 'date_range_days', label: '时间跨度', fmt: (v: number) => `${v}天` },
            { key: 'single_source_pct', label: '单源依赖', fmt: (v: number) => `${(v * 100).toFixed(0)}%` },
          ].filter(s => stats[s.key] !== undefined).map(s => (
            <motion.div
              key={s.key}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                padding: '10px 12px', background: 'var(--bg-deep)',
                borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)',
              }}
            >
              <div style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginBottom: 4 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                {s.fmt(stats[s.key] as number)}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Gap cards */}
      {gaps.length === 0 && (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>
          未发现明显情报缺口
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
        {gaps.map((g, i) => {
          const sev = SEVERITY_CONFIG[g.severity] ?? SEVERITY_CONFIG.low
          const Icon = GAP_ICONS[g.gap_type] ?? Warning
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              style={{
                padding: '12px 14px',
                background: sev.bg,
                border: `1px solid ${sev.color}22`,
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{ marginTop: 1 }}>
                  {g.severity === 'critical' || g.severity === 'high'
                    ? <Warning size={16} weight="fill" color={sev.color} />
                    : <WarningCircle size={14} weight="duotone" color={sev.color} />
                  }
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 9, color: sev.color, fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <Icon size={10} weight="duotone" color={sev.color} />
                      {GAP_LABELS[g.gap_type] ?? g.gap_type}
                    </span>
                    <span style={{
                      fontSize: 8, fontWeight: 700, padding: '1px 6px',
                      borderRadius: 99, background: `${sev.color}22`, color: sev.color,
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {sev.label}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 4 }}>
                    {g.description}
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--accent)', fontFamily: 'var(--font-ui)' }}>
                    → {g.recommendation}
                  </div>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      <AIInterpretBadge
        analysisType="gap_analysis"
        context={{ gap_count: gaps.length, critical_gaps: gaps.filter(g => g.severity === 'critical').length, coverage_stats: stats }}
      />
    </div>
  )
}
