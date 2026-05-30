import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { X, ChartBar, Globe, Hash, Stack } from '@phosphor-icons/react'
import { fetchStats } from '../api'
import type { DashboardStats } from '../types'
import { LAYER_META } from '../types'

interface Props { onClose: () => void; isMobile?: boolean }

function SimpleBar({ data, color, max }: { data: Array<{ label: string; value: number }>; color: string; max: number }) {
  const h = 120
  const w = '100%'
  const barW = 20
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      {data.map((d, i) => {
        const barH = max > 0 ? (d.value / max) * (h - 20) : 0
        return (
          <motion.g key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03, duration: 0.3 }}
          >
            <motion.rect
              initial={{ height: 0 }}
              animate={{ height: barH }}
              transition={{ delay: i * 0.03, duration: 0.4, ease: 'easeOut' }}
              x={i * (barW + 4) + 2}
              y={h - 10 - barH}
              width={barW}
              rx={3}
              fill={color}
              opacity={0.6}
            />
            {i % Math.max(1, Math.floor(data.length / 6)) === 0 && (
              <text x={i * (barW + 4) + barW / 2} y={h - 2} textAnchor="middle" fill="var(--text-tertiary)"
                fontSize={7} fontFamily="'JetBrains Mono', monospace">
                {d.label.length > 5 ? d.label.slice(0, 5) + '…' : d.label}
              </text>
            )}
          </motion.g>
        )
      })}
    </svg>
  )
}

export default function StatsPanel({ onClose, isMobile }: Props) {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchStats().then(d => { setStats(d); setLoading(false) }).catch(e => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [])

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.05, delayChildren: 0.1 } },
  }

  const itemVariants = {
    hidden: { y: 12, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { type: 'spring' as const, stiffness: 100, damping: 20 } },
  }

  return (
    <motion.div
      initial={{ y: 20, opacity: 0, scale: 0.97 }}
      animate={{ y: 0, opacity: 1, scale: 1 }}
      exit={{ y: 20, opacity: 0, scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      className={isMobile ? 'glass-panel mobile-full-panel' : 'glass-panel'}
      style={{
        position: 'fixed',
        bottom: isMobile ? 0 : 16,
        left: isMobile ? 0 : '50%',
        transform: isMobile ? 'none' : 'translateX(-50%)',
        width: isMobile ? '100%' : 660,
        maxWidth: isMobile ? '100%' : '94vw',
        maxHeight: isMobile ? '100%' : '80vh',
        borderRadius: isMobile ? 0 : 'var(--radius-lg)',
        zIndex: 1000, overflow: 'hidden',
        boxShadow: 'var(--shadow-diffuse)',
        fontFamily: 'var(--font-ui)',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 18px', borderBottom: '1px solid var(--glass-border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ChartBar size={16} weight="duotone" color="var(--accent)" />
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 1, fontFamily: 'var(--font-display)' }}>
            情报数据看板
          </span>
        </div>
        <motion.button
          whileHover={{ scale: 1.1, rotate: 90 }}
          whileTap={{ scale: 0.9 }}
          onClick={onClose}
          className="interactive-btn"
          style={{
            background: 'rgba(0,0,0,0.04)', border: '1px solid var(--glass-border)',
            color: 'var(--text-tertiary)', cursor: 'pointer',
            width: 28, height: 28, borderRadius: 'var(--radius-sm)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}
        >
          <X size={12} weight="bold" />
        </motion.button>
      </div>

      {/* Content */}
      <div style={{ padding: '14px 18px', overflowY: 'auto', maxHeight: 'calc(80vh - 52px)' }}>
        {loading && (
          <div style={{ padding: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
              style={{
                width: 20, height: 20, borderRadius: '50%',
                border: '2px solid var(--border-subtle)',
                borderTopColor: 'var(--accent)',
              }}
            />
            <span style={{ color: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              加载情报数据...
            </span>
          </div>
        )}
        {error && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--danger)', fontSize: 11 }}>
            {error}
          </div>
        )}
        {stats && (
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            style={{ display: 'flex', flexDirection: 'column', gap: 20 }}
          >
            {/* Bento Grid: Summary cards */}
            <motion.div variants={itemVariants} style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10,
            }}>
              {[
                { label: '情报总量', value: stats.total_items, icon: ChartBar, color: 'var(--accent)' },
                { label: '数据来源', value: stats.total_sources, icon: Globe, color: 'var(--info)' },
                { label: '活跃图层', value: stats.by_layer.filter(l => l.count > 0).length, icon: Stack, color: 'var(--warning)' },
              ].map(card => (
                <div key={card.label} style={{
                  background: 'var(--bg-deep)', borderRadius: 'var(--radius-md)',
                  padding: '14px 16px',
                  border: '1px solid var(--glass-border)',
                  boxShadow: 'var(--glass-inner-shadow)',
                }}>
                  <div style={{
                    fontSize: 9, color: 'var(--text-tertiary)',
                    fontFamily: 'var(--font-mono)', letterSpacing: 1,
                    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6,
                  }}>
                    <card.icon size={12} weight="duotone" color={card.color} />
                    {card.label}
                  </div>
                  <motion.div
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ type: 'spring', stiffness: 100, damping: 12, delay: 0.2 }}
                    style={{ fontSize: 28, fontWeight: 700, color: card.color, fontFamily: 'var(--font-display)' }}
                  >
                    {card.value}
                  </motion.div>
                </div>
              ))}
            </motion.div>

            {/* Layer breakdown */}
            <motion.div variants={itemVariants}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)', letterSpacing: 0.5 }}>
                图层分布
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {stats.by_layer.filter(l => l.count > 0).map((l, i) => {
                  const meta = LAYER_META[l.layer]
                  const pct = stats.total_items > 0 ? (l.count / stats.total_items) * 100 : 0
                  return (
                    <motion.div
                      key={l.layer}
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: '100%', opacity: 1 }}
                      transition={{ delay: 0.3 + i * 0.04 }}
                      style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                    >
                      <span style={{ fontSize: 10, color: meta.color, fontWeight: 600, minWidth: 44, fontFamily: 'var(--font-mono)' }}>
                        {meta.label}
                      </span>
                      <div style={{ flex: 1, height: 6, background: 'var(--bg-deep)', borderRadius: 3, overflow: 'hidden' }}>
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: 0.4 + i * 0.04, duration: 0.6, ease: 'easeOut' }}
                          style={{ height: '100%', background: meta.color, borderRadius: 3, opacity: 0.6 }}
                        />
                      </div>
                      <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', minWidth: 30, textAlign: 'right' }}>
                        {l.count}
                      </span>
                    </motion.div>
                  )
                })}
              </div>
            </motion.div>

            {/* Daily trend + Geo distribution in a 2-column grid */}
            <motion.div variants={itemVariants} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {stats.daily_trend.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)', letterSpacing: 0.5 }}>
                    每日采集趋势
                  </div>
                  <SimpleBar
                    data={stats.daily_trend.map(d => ({ label: d.date.slice(5), value: d.count }))}
                    color="var(--accent)"
                    max={Math.max(...stats.daily_trend.map(d => d.count), 1)}
                  />
                </div>
              )}
              {stats.geo_distribution.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)', letterSpacing: 0.5 }}>
                    地理分布 TOP 10
                  </div>
                  <SimpleBar
                    data={stats.geo_distribution.slice(0, 10).map(g => ({ label: g.country, value: g.count }))}
                    color="var(--warning)"
                    max={Math.max(...stats.geo_distribution.slice(0, 10).map(g => g.count), 1)}
                  />
                </div>
              )}
            </motion.div>

            {/* Source matrix */}
            {stats.source_matrix.length > 0 && (
              <motion.div variants={itemVariants}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)', letterSpacing: 0.5 }}>
                  来源评估矩阵
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {stats.source_matrix.slice(0, 15).map((s, i) => (
                    <motion.div
                      key={s.name}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '4px 10px', background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <span style={{ fontSize: 10, color: 'var(--text-primary)', fontWeight: 500, minWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-ui)' }}>
                        {s.name}
                      </span>
                      <span style={{
                        fontSize: 9, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: s.credibility >= 0.7 ? 'var(--success)' : s.credibility >= 0.5 ? 'var(--warning)' : 'var(--danger)',
                        minWidth: 30,
                      }}>
                        {Math.round(s.credibility * 100)}
                      </span>
                      <div style={{ flex: 1, height: 4, background: 'var(--bg-surface)', borderRadius: 2, overflow: 'hidden' }}>
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.round(s.credibility * 100)}%` }}
                          transition={{ delay: i * 0.03, duration: 0.4 }}
                          style={{
                            height: '100%',
                            background: s.credibility >= 0.7 ? 'var(--success)' : s.credibility >= 0.5 ? 'var(--warning)' : 'var(--danger)',
                            borderRadius: 2,
                          }}
                        />
                      </div>
                      <span style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', minWidth: 24, textAlign: 'right' }}>
                        {s.document_count}
                      </span>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Top keywords as tag cloud */}
            {stats.top_keywords.length > 0 && (
              <motion.div variants={itemVariants}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Hash size={12} weight="duotone" />
                  高频关键词
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {stats.top_keywords.slice(0, 30).map((k, i) => {
                    const maxCount = stats.top_keywords[0]?.count ?? 1
                    const size = 9 + (k.count / maxCount) * 6
                    const op = 0.35 + (k.count / maxCount) * 0.65
                    return (
                      <motion.span
                        key={k.word}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: op, scale: 1 }}
                        transition={{ delay: i * 0.02 }}
                        style={{
                          fontSize: size, color: `rgba(13,148,136,${op})`,
                          fontFamily: 'var(--font-mono)',
                          padding: '1px 6px',
                          cursor: 'default',
                        }}
                      >
                        {k.word}
                      </motion.span>
                    )
                  })}
                </div>
              </motion.div>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
