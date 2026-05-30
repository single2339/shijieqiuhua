import { useState } from 'react'
import { motion } from 'framer-motion'
import { FileText, Article, X, ArrowsClockwise } from '@phosphor-icons/react'
import { generateReport } from '../api'
import type { SituationReport, IntelLayer } from '../types'
import { LAYER_META } from '../types'

interface Props { onClose: () => void; isMobile?: boolean }

const ALL_LAYERS: IntelLayer[] = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber']
const DETAIL_LEVELS = [
  { value: 'brief', label: '简报' },
  { value: 'standard', label: '标准' },
  { value: 'deep', label: '深度' },
]

export default function ReportPanel({ onClose, isMobile }: Props) {
  const [topic, setTopic] = useState('')
  const [country, setCountry] = useState('')
  const [days, setDays] = useState(7)
  const [layer, setLayer] = useState('')
  const [detail, setDetail] = useState('standard')
  const [report, setReport] = useState<SituationReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setReport(null)
    try {
      const r = await generateReport({ topic: topic || undefined, country: country || undefined, days, layer: layer || undefined, detail_level: detail })
      setReport(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
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
          <Article size={16} weight="duotone" color="var(--accent)" />
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 1, fontFamily: 'var(--font-display)' }}>
            态势简报生成
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
        {!report && !loading && !error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
          >
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={topic} onChange={e => setTopic(e.target.value)}
                className="panel-input"
                placeholder="主题（如：川普访华）"
                style={{
                  flex: 1, background: 'var(--bg-deep)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 'var(--radius-sm)',
                  fontSize: 11, fontFamily: 'var(--font-ui)', outline: 'none',
                }}
              />
              <input value={country} onChange={e => setCountry(e.target.value)}
                className="panel-input"
                placeholder="国家（可选）"
                style={{
                  width: 140, background: 'var(--bg-deep)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 'var(--radius-sm)',
                  fontSize: 11, fontFamily: 'var(--font-ui)', outline: 'none',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <select value={layer} onChange={e => setLayer(e.target.value)}
                className="panel-select"
                style={{
                  flex: 1, background: 'var(--bg-deep)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 'var(--radius-sm)',
                  fontSize: 11, fontFamily: 'var(--font-mono)',
                }}>
                <option value="">全部图层</option>
                {ALL_LAYERS.map(l => (
                  <option key={l} value={l}>{LAYER_META[l].label}</option>
                ))}
              </select>
              <select value={days} onChange={e => setDays(Number(e.target.value))}
                className="panel-select"
                style={{
                  width: 100, background: 'var(--bg-deep)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 'var(--radius-sm)',
                  fontSize: 11, fontFamily: 'var(--font-mono)',
                }}>
                {[1, 3, 7, 14, 30].map(n => (
                  <option key={n} value={n}>过去{n}天</option>
                ))}
              </select>
              <select value={detail} onChange={e => setDetail(e.target.value)}
                className="panel-select"
                style={{
                  width: 80, background: 'var(--bg-deep)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 'var(--radius-sm)',
                  fontSize: 11, fontFamily: 'var(--font-mono)',
                }}>
                {DETAIL_LEVELS.map(d => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleGenerate}
              style={{
                background: 'var(--accent)', border: 'none', color: '#fff',
                padding: '9px 0', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)',
                letterSpacing: 1, marginTop: 4, display: 'flex', alignItems: 'center',
                justifyContent: 'center', gap: 6,
              }}
            >
              <ArrowsClockwise size={14} weight="bold" />
              生成简报
            </motion.button>
          </motion.div>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
              style={{
                width: 24, height: 24, borderRadius: '50%',
                border: '2px solid var(--border-subtle)',
                borderTopColor: 'var(--accent)',
                margin: '0 auto 12px',
              }}
            />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              正在分析情报数据，生成态势简报...
            </span>
          </div>
        )}

        {error && (
          <div style={{ textAlign: 'center', padding: 20, color: 'var(--danger)', fontSize: 11 }}>
            {error}
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => { setError(null); setReport(null) }}
              style={{
                display: 'block', margin: '12px auto 0',
                background: 'var(--bg-surface)', border: '1px solid var(--glass-border)',
                color: 'var(--text-primary)', padding: '5px 14px', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', fontSize: 10, fontFamily: 'var(--font-mono)',
              }}
            >
              返回
            </motion.button>
          </div>
        )}

        {report && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginBottom: 12, padding: '8px 12px',
              background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
              fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <FileText size={12} weight="duotone" color="var(--accent)" />
                {report.title}
              </span>
              <span>情报: {report.item_count} / 来源: {report.source_count}</span>
              <span>{report.generated_at?.slice(0, 16).replace('T', ' ')}</span>
            </div>

            <div style={{
              padding: '12px 14px', background: 'rgba(16,185,129,0.04)',
              border: '1px solid rgba(16,185,129,0.12)', borderRadius: 'var(--radius-md)',
              fontSize: 11, lineHeight: 1.6, color: 'var(--text-primary)',
              marginBottom: 12,
            }}>
              {report.summary}
            </div>

            {report.sections.map((sec, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.05 }}
                style={{
                  marginBottom: 10, padding: '10px 14px',
                  background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--glass-border)',
                }}
              >
                <div style={{
                  fontSize: 11, fontWeight: 600, color: 'var(--accent)',
                  marginBottom: 6, letterSpacing: 0.5, fontFamily: 'var(--font-display)',
                }}>
                  {sec.heading.replace(/^#+\s*/g, '')}
                </div>
                <div style={{
                  fontSize: 11, lineHeight: 1.6, color: 'var(--text-primary)',
                  whiteSpace: 'pre-wrap',
                }}>
                  {sec.body}
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
