import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import type { CorroborationResult, SourcePairOverlap } from '../../types'
import { fetchCorroboration } from '../../api'
import AIInterpretBadge from './AIInterpretBadge'

function heatColor(score: number): string {
  if (score >= 0.8) return '#10b981'
  if (score >= 0.6) return '#34d399'
  if (score >= 0.4) return '#6ee7b7'
  if (score >= 0.2) return '#a7f3d0'
  return '#064e3b'
}

export default function CorroborationView() {
  const [data, setData] = useState<CorroborationResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPair, setSelectedPair] = useState<SourcePairOverlap | null>(null)
  const [hoverCell, setHoverCell] = useState<{ i: number; j: number } | null>(null)

  useEffect(() => {
    fetchCorroboration()
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

  if (!data || data.sources.length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>暂无信源数据</div>
  }

  const { sources, matrix } = data
  const n = sources.length
  const cellSize = Math.max(16, Math.min(28, Math.floor(400 / n)))

  return (
    <div>
      <div style={{ overflow: 'auto', borderRadius: 'var(--radius-md)', background: 'var(--bg-deep)', marginBottom: 12 }}>
        <svg width={n * cellSize + 100} height={n * cellSize + 100} style={{ display: 'block' }}>
          {/* Y-axis labels */}
          {sources.map((s, i) => (
            <text
              key={`y-${i}`}
              x={94}
              y={i * cellSize + 50 + cellSize / 2}
              textAnchor="end"
              fill="var(--text-tertiary)"
              fontSize={8}
              fontFamily="'JetBrains Mono', monospace"
            >
              {s.length > 12 ? s.slice(0, 12) + '…' : s}
            </text>
          ))}
          {/* X-axis labels (rotated) */}
          {sources.map((s, i) => (
            <text
              key={`x-${i}`}
              x={i * cellSize + 100 + cellSize / 2}
              y={n * cellSize + 55}
              textAnchor="end"
              fill="var(--text-tertiary)"
              fontSize={8}
              fontFamily="'JetBrains Mono', monospace"
              transform={`rotate(-45 ${i * cellSize + 100 + cellSize / 2} ${n * cellSize + 55})`}
            >
              {s.length > 12 ? s.slice(0, 12) + '…' : s}
            </text>
          ))}
          {/* Matrix cells */}
          {matrix.map((row, i) =>
            row.map((score, j) => {
              const isHovered = hoverCell?.i === i && hoverCell?.j === j
              return (
                <motion.rect
                  key={`${i}-${j}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: (i * n + j) * 0.0005 }}
                  x={j * cellSize + 100}
                  y={i * cellSize + 30}
                  width={cellSize - 1}
                  height={cellSize - 1}
                  rx={2}
                  fill={heatColor(score)}
                  opacity={isHovered ? 1 : 0.7}
                  stroke={isHovered ? 'var(--text-primary)' : 'none'}
                  strokeWidth={1}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoverCell({ i, j })}
                  onMouseLeave={() => setHoverCell(null)}
                  onClick={() => {
                    const pair = data.top_pairs.find(
                      p => (p.source_a === sources[i] && p.source_b === sources[j]) ||
                        (p.source_a === sources[j] && p.source_b === sources[i])
                    )
                    if (pair) setSelectedPair(pair)
                  }}
                >
                  <title>{`${sources[i]} × ${sources[j]}: ${(score * 100).toFixed(0)}%`}</title>
                </motion.rect>
              )
            })
          )}
        </svg>
      </div>

      {/* Selected pair detail */}
      {selectedPair && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            padding: '10px 14px', marginBottom: 10,
            background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--glass-border)',
            fontSize: 11, color: 'var(--text-secondary)',
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            {selectedPair.source_a} ↔ {selectedPair.source_b}
          </div>
          <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
            <span>共享主题: <b style={{ color: 'var(--accent)' }}>{selectedPair.shared_topics}</b></span>
            <span>一致度: <b style={{ color: heatColor(selectedPair.agreement_score) }}>{(selectedPair.agreement_score * 100).toFixed(0)}%</b></span>
          </div>
        </motion.div>
      )}

      {/* Top pairs list */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
          TOP 10 信源对一致度
        </div>
        {data.top_pairs.slice(0, 10).map((p, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.03 }}
            onClick={() => setSelectedPair(p)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '3px 8px', cursor: 'pointer',
              borderRadius: 'var(--radius-sm)',
              background: selectedPair === p ? 'rgba(16,185,129,0.08)' : 'transparent',
              fontSize: 10,
            }}
          >
            <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{p.source_a} ↔ {p.source_b}</span>
            <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 9 }}>
              共享 {p.shared_topics}
            </span>
            <span style={{
              color: heatColor(p.agreement_score),
              fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600, minWidth: 36, textAlign: 'right',
            }}>
              {(p.agreement_score * 100).toFixed(0)}%
            </span>
          </motion.div>
        ))}
      </div>

      <AIInterpretBadge
        analysisType="corroboration"
        context={{ source_count: sources.length, top_pair_score: data.top_pairs[0]?.agreement_score ?? 0 }}
      />
    </div>
  )
}
