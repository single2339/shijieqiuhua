import { useEffect, useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { TimelineResult } from '../../types'
import { LAYER_META } from '../../types'
import { fetchTimeline } from '../../api'
import AIInterpretBadge from './AIInterpretBadge'

interface Props {
  startDate?: string
  endDate?: string
}

const LAYERS = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber'] as const
const ROW_H = 28
const LEFT_PAD = 50

export default function TimelineView({ startDate, endDate }: Props) {
  const [data, setData] = useState<TimelineResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [layerFilter, setLayerFilter] = useState('')
  const [zoom, setZoom] = useState(1)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLoading(true)
    fetchTimeline(startDate, endDate, layerFilter || undefined)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [startDate, endDate, layerFilter])

  const points = data?.points ?? []
  const maxCount = Math.max(...points.map(p => p.count), 1)
  const totalH = LAYERS.length * ROW_H + 40

  const renderSvg = useCallback(() => {
    if (points.length === 0) return null
    const w = Math.max(points.length * (20 * zoom), 600)
    return (
      <svg width={w} height={totalH} style={{ display: 'block', minWidth: '100%' }}>
        {/* Layer labels */}
        {LAYERS.map((layer, i) => {
          const meta = LAYER_META[layer]
          return (
            <text
              key={layer}
              x={LEFT_PAD - 8}
              y={i * ROW_H + 20 + ROW_H / 2}
              textAnchor="end"
              fill={meta.color}
              fontSize={9}
              fontFamily="'JetBrains Mono', monospace"
              opacity={0.7}
            >
              {meta.label}
            </text>
          )
        })}
        {/* Grid lines */}
        {LAYERS.map((_, i) => (
          <line
            key={`grid-${i}`}
            x1={LEFT_PAD} y1={i * ROW_H + 20}
            x2={w} y2={i * ROW_H + 20}
            stroke="var(--border-subtle)"
            strokeWidth={0.5}
            opacity={0.3}
          />
        ))}
        {/* Date labels */}
        {points.map((p, pi) => {
          const showLabel = points.length <= 30 || pi % Math.ceil(points.length / 15) === 0
          return showLabel ? (
            <text
              key={`dl-${pi}`}
              x={LEFT_PAD + pi * (20 * zoom) + (10 * zoom)}
              y={totalH - 4}
              textAnchor="middle"
              fill="var(--text-tertiary)"
              fontSize={7}
              fontFamily="'JetBrains Mono', monospace"
            >
              {p.date.slice(5)}
            </text>
          ) : null
        })}
        {/* Event dots */}
        {points.map((p, pi) => {
          const x = LEFT_PAD + pi * (20 * zoom) + (10 * zoom)
          return LAYERS.map((layer, li) => {
            const count = p.layer_counts[layer] ?? 0
            if (count === 0) return null
            const meta = LAYER_META[layer]
            const r = Math.max(2, Math.min(8, (count / maxCount) * 8 * zoom))
            const y = li * ROW_H + 20 + ROW_H / 2
            return (
              <motion.circle
                key={`${pi}-${li}`}
                initial={{ r: 0 }}
                animate={{ r }}
                transition={{ delay: pi * 0.005, duration: 0.2 }}
                cx={x}
                cy={y}
                fill={meta.color}
                opacity={0.75}
                style={{ cursor: 'pointer' }}
              >
                <title>{`${p.date} — ${meta.label}: ${count}`}</title>
              </motion.circle>
            )
          })
        })}
      </svg>
    )
  }, [points, zoom, maxCount, totalH])

  return (
    <div>
      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <select
          value={layerFilter}
          onChange={e => setLayerFilter(e.target.value)}
          style={{
            background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
            borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
            padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)',
          }}
        >
          <option value="">全部图层</option>
          {LAYERS.map(l => (
            <option key={l} value={l}>{LAYER_META[l].label}</option>
          ))}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}
            style={{
              background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--text-secondary)',
              padding: '2px 8px', cursor: 'pointer', fontSize: 12,
            }}
          >−</button>
          <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', minWidth: 30, textAlign: 'center' }}>
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom(z => Math.min(3, z + 0.25))}
            style={{
              background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--text-secondary)',
              padding: '2px 8px', cursor: 'pointer', fontSize: 12,
            }}
          >+</button>
        </div>
      </div>

      {loading && (
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
      )}

      {error && <div style={{ color: 'var(--danger)', fontSize: 11, textAlign: 'center', padding: 20 }}>{error}</div>}

      {!loading && !error && points.length === 0 && (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>
          暂无时间线数据
        </div>
      )}

      {!loading && !error && points.length > 0 && (
        <>
          <div ref={scrollRef} style={{ overflowX: 'auto', overflowY: 'hidden', borderRadius: 'var(--radius-md)', background: 'var(--bg-deep)' }}>
            {renderSvg()}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
            {data?.date_range ? `${data.date_range.start} → ${data.date_range.end} (${data.date_range.days} 天)` : ''}
          </div>
          <AIInterpretBadge
            analysisType="timeline"
            context={{ point_count: points.length, layer_filter: layerFilter || 'all', date_range: data?.date_range ?? {} }}
          />
        </>
      )}
    </div>
  )
}
