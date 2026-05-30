import { useState } from 'react'
import { motion } from 'framer-motion'
import { X, MapPin, Clock, Code, CaretRight, FileText, Info } from '@phosphor-icons/react'
import type { IntelItem, BayesianEvidenceItem } from '../types'
import { LAYER_META } from '../types'

interface Props { item: IntelItem; onClose: () => void; isMobile?: boolean }

function VerdictBadge({ verdict }: { verdict: IntelItem['verdict'] }) {
  const cfg = {
    verified: { color: 'var(--success)', bg: 'rgba(16,185,129,0.08)', label: '已核实' },
    false: { color: 'var(--danger)', bg: 'rgba(220,38,38,0.08)', label: '虚假' },
    uncertain: { color: 'var(--warning)', bg: 'rgba(217,119,6,0.08)', label: '不确定' },
  }[verdict]
  return (
    <span style={{
      background: cfg.bg, color: cfg.color,
      padding: '2px 10px', borderRadius: 'var(--radius-sm)', fontSize: 9,
      fontWeight: 700, letterSpacing: 1.5,
      border: `1px solid ${cfg.color}33`,
      fontFamily: 'var(--font-mono)',
    }}>
      {cfg.label}
    </span>
  )
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  const color = pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginBottom: 3,
        fontFamily: 'var(--font-mono)', fontSize: 9,
        color: 'var(--text-secondary)', letterSpacing: 0.5,
      }}>
        <span>置信度</span>
        <span style={{ color, fontWeight: 700 }}>{pct}%</span>
      </div>
      <div style={{
        height: 3, background: 'var(--bg-deep)', borderRadius: 2,
        overflow: 'hidden', position: 'relative',
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          style={{
            height: '100%',
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            borderRadius: 2,
          }}
        />
      </div>
    </div>
  )
}

function BayesianChart({ trace, confidence }: { trace: number[]; confidence: number }) {
  if (!trace.length) return null
  const w = 200; const h = 44
  const maxV = Math.max(...trace, 0.01)
  const pts = trace.map((v, i) => {
    const x = trace.length > 1 ? (i / (trace.length - 1)) * w : w / 2
    return `${x},${h - (v / maxV) * (h - 6) - 3}`
  }).join(' ')
  const lastColor = confidence >= 0.7 ? '#059669' : confidence >= 0.4 ? '#d97706' : '#dc2626'

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 9,
        color: 'var(--text-secondary)', marginBottom: 4, letterSpacing: 0.5,
      }}>
        置信度更新轨迹（{trace.length} 次评估）
      </div>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
        <rect x={0} y={0} width={w} height={h} rx={3} fill="var(--bg-deep)" />
        {[0.25, 0.5, 0.75].map(t => (
          <line key={t} x1={0} y1={h - t * (h - 6) - 3}
            x2={w} y2={h - t * (h - 6) - 3}
            stroke="rgba(156,143,130,0.18)" strokeWidth={0.5} />
        ))}
        <polygon
          points={`0,${h} ${pts} ${w},${h}`}
          fill={`${lastColor}12`}
        />
        <polyline points={pts} fill="none" stroke={lastColor} strokeWidth={1.5} strokeLinejoin="round" />
        {trace.map((v, i) => {
          const x = trace.length > 1 ? (i / (trace.length - 1)) * w : w / 2
          const y = h - (v / maxV) * (h - 6) - 3
          const isLast = i === trace.length - 1
          return (
            <circle key={i} cx={x} cy={y} r={isLast ? 3.5 : 1.5}
              fill={isLast ? lastColor : 'var(--text-secondary)'}
              stroke={isLast ? 'var(--bg-deep)' : 'none'}
              strokeWidth={isLast ? 1.5 : 0}
            />
          )
        })}
      </svg>
    </div>
  )
}

const TIER_COLORS: Record<string, string> = {
  A: '#059669', B: '#0891b2', C: '#d97706', D: '#dc2626', E: '#9c8f82',
}

function QualityBadge({ tier }: { tier: string }) {
  const c = TIER_COLORS[tier] ?? '#9c8f82'
  return <span style={{
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    width: 18, height: 18, borderRadius: 'var(--radius-sm)',
    background: c, color: '#fff', fontSize: 9, fontWeight: 800,
    fontFamily: 'var(--font-mono)',
    lineHeight: '18px', flexShrink: 0,
  }}>{tier}</span>
}

function BayesianDetail({ item }: { item: IntelItem }) {
  const [open, setOpen] = useState(false)
  const evidence = item.bayesian_evidence_items
  if (!evidence?.length) return null

  const dirIcon = (d: string) => d === 'against' ? '↧' : '↥'
  const dirColor = (d: string) => d === 'against' ? 'var(--danger)' : 'var(--success)'

  return (
    <div style={{ marginTop: 8, borderTop: '1px solid var(--border-subtle)', paddingTop: 8 }}>
      <motion.button
        whileTap={{ scale: 0.98 }}
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
          background: 'none', border: 'none', padding: 0, width: '100%',
          fontFamily: 'var(--font-mono)', fontSize: 9,
          color: 'var(--text-secondary)', letterSpacing: 0.5,
        }}
      >
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.2 }}
          style={{ display: 'inline-flex' }}
        >
          <CaretRight size={10} weight="bold" />
        </motion.span>
        推理详情
        <span style={{
          background: 'var(--bg-deep)', color: 'var(--text-tertiary)',
          padding: '0 6px', borderRadius: 3, fontSize: 8,
        }}>
          {item.bayesian_method || 'odds-update'}
        </span>
        {item.bayesian_prior_quality && (
          <QualityBadge tier={item.bayesian_prior_quality} />
        )}
        <span style={{ flex: 1, textAlign: 'right', fontSize: 8, color: 'var(--text-tertiary)' }}>
          {evidence.length} 条
        </span>
      </motion.button>

      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          style={{ marginTop: 6, fontSize: 10, color: 'var(--text-primary)', overflow: 'hidden' }}
        >
          {item.bayesian_prior_class && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 8px', background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
              marginBottom: 6, fontSize: 9,
            }}>
              <span style={{ color: 'var(--text-tertiary)' }}>先验:</span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {item.bayesian_prior_class.replace('-', ' ')}
              </span>
              {item.bayesian_prior_quality && <QualityBadge tier={item.bayesian_prior_quality} />}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {evidence.map((ei: BayesianEvidenceItem, i: number) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '3px 8px',
                background: i % 2 === 0 ? 'transparent' : 'var(--bg-deep)',
                borderRadius: 3,
              }}>
                <QualityBadge tier={ei.quality} />
                <span style={{
                  flex: 1, overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap', fontSize: 10, fontWeight: 500,
                }}>
                  {{
                    'content-specificity': '内容特异性',
                    'cross-source': '跨来源印证',
                    'temporal': '时间新鲜度',
                    'verifiable-numbers': '可验证数据',
                  }[ei.name] || ei.name}
                </span>
                <span style={{ color: 'var(--text-tertiary)', fontSize: 9, fontFamily: 'var(--font-mono)' }}>
                  LR={ei.lr}
                </span>
                {ei.dep_discount < 1 && (
                  <span style={{ color: 'var(--text-tertiary)', fontSize: 8, fontFamily: 'var(--font-mono)' }}>
                    ×{ei.dep_discount}
                  </span>
                )}
                <span style={{ color: dirColor(ei.direction), fontWeight: 700, fontSize: 11 }}>
                  {dirIcon(ei.direction)}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}

function SourceListPopover({ sources }: { sources: string[] }) {
  const [open, setOpen] = useState(false)
  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          padding: 0, display: 'inline-flex', alignItems: 'center',
        }}
      >
        <Info size={10} weight="duotone" color="var(--text-tertiary)" />
      </button>
      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            style={{ position: 'fixed', inset: 0, zIndex: 1099 }}
          />
          <div style={{
            position: 'absolute', bottom: '120%', left: 0, zIndex: 1100,
            background: 'var(--bg-surface)', border: '1px solid var(--glass-border)',
            borderRadius: 'var(--radius-sm)', padding: '6px 10px',
            boxShadow: 'var(--shadow-diffuse)', minWidth: 120,
          }}>
            {sources.map((s, i) => (
              <div key={s} style={{
                fontSize: 10, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)',
                padding: '3px 0',
                borderBottom: i < sources.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                whiteSpace: 'nowrap',
              }}>
                {s}
              </div>
            ))}
          </div>
        </>
      )}
    </span>
  )
}

export default function IntelCard({ item, onClose, isMobile }: Props) {
  const meta = LAYER_META[item.layer]
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const longSummary = item.summary.length > 120

  return (
    <motion.div
      initial={{ y: 20, opacity: 0, scale: 0.96 }}
      animate={{ y: 0, opacity: 1, scale: 1 }}
      exit={{ y: 20, opacity: 0, scale: 0.96 }}
      transition={{ type: 'spring', stiffness: 120, damping: 22 }}
      className={isMobile ? 'glass-panel mobile-bottom-sheet' : 'glass-panel'}
      style={{
        position: 'fixed',
        bottom: isMobile ? 0 : 16,
        left: isMobile ? 0 : '50%',
        transform: isMobile ? 'none' : 'translateX(-50%)',
        width: isMobile ? '100%' : 520,
        maxWidth: isMobile ? '100%' : '92vw',
        maxHeight: isMobile ? '80vh' : undefined,
        overflowY: isMobile ? 'auto' : undefined,
        borderRadius: isMobile ? 'var(--radius-lg) var(--radius-lg) 0 0' : 'var(--radius-lg)',
        padding: isMobile ? 14 : 16, zIndex: 1000,
        border: `1px solid ${meta.color}22`,
        boxShadow: `var(--shadow-diffuse), 0 0 60px rgba(16,185,129,0.03)`,
        fontFamily: 'var(--font-ui)',
      }}
    >
      {/* Top row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontFamily: 'var(--font-mono)',
              fontSize: 9, fontWeight: 700, letterSpacing: 1.5,
              color: meta.color,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: meta.color,
                boxShadow: `0 0 6px ${meta.color}55`,
              }} />
              {meta.label.toUpperCase()}
            </span>
            <VerdictBadge verdict={item.verdict} />
            <span style={{
              fontSize: 9, color: 'var(--text-tertiary)',
              fontFamily: 'var(--font-mono)',
            }}>
              #{item.evidence_count}
            </span>
          </div>
          <h3 style={{
            margin: 0, fontSize: isMobile ? 15 : 14, fontWeight: 600,
            color: 'var(--text-primary)', lineHeight: 1.3,
            fontFamily: 'var(--font-display)',
          }}>
            {item.title}
          </h3>
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
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginLeft: 12, flexShrink: 0,
          }}
        >
          <X size={12} weight="bold" />
        </motion.button>
      </div>

      {/* Location + Time */}
      <div style={{
        display: 'flex', gap: 12, marginTop: 6,
        fontFamily: 'var(--font-mono)', fontSize: 10,
        color: 'var(--text-secondary)', alignItems: 'center',
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <MapPin size={12} weight="duotone" color="var(--text-tertiary)" />
          {item.location_name} · {item.country}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Clock size={12} weight="duotone" color="var(--text-tertiary)" />
          {item.captured_at?.slice(0, 10)}
        </span>
      </div>

      {/* Confidence */}
      <ConfidenceBar confidence={item.confidence} />
      <BayesianChart trace={item.bayesian_trace} confidence={item.confidence} />
      <BayesianDetail item={item} />

      {/* Summary */}
      <div>
        <p style={{
          fontSize: 12, color: 'var(--text-primary)', margin: '8px 0',
          lineHeight: 1.6,
          maxHeight: summaryExpanded ? 'none' : 60,
          overflow: 'hidden',
          transition: 'max-height 0.25s ease',
        }}>
          {item.summary}
        </p>
        {longSummary && (
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={() => setSummaryExpanded(v => !v)}
            style={{
              background: 'none', border: 'none', color: 'var(--accent)',
              cursor: 'pointer', fontSize: 10, padding: 0,
              fontFamily: 'var(--font-mono)',
            }}
          >
            {summaryExpanded ? '收起 ▲' : '展开 ▼'}
          </motion.button>
        )}
      </div>

      {/* Footer */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        paddingTop: 8, borderTop: '1px solid var(--border-subtle)',
        fontFamily: 'var(--font-mono)', fontSize: 9,
      }}>
        <span style={{ color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Code size={10} weight="duotone" color="var(--text-tertiary)" />
          来源: <span style={{ color: meta.color }}>{item.source_system}</span>
          {item.sources.length > 1 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{ color: 'var(--text-tertiary)' }}>+{item.sources.length - 1}</span>
              <SourceListPopover sources={item.sources} />
            </span>
          )}
        </span>
        <span style={{ color: 'var(--text-tertiary)' }}>
          {item.sources.length > 1 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <FileText size={10} weight="duotone" />
              {item.sources.length} 条引用
            </span>
          )}
        </span>
      </div>
    </motion.div>
  )
}
