import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, Target, WarningCircle } from '@phosphor-icons/react'
import { fetchWarningIndicators } from '../../api'
import type { BriefWorkspaceMaterial, IntelLayer, WarningIndicator, WarningIndicatorResult } from '../../types'
import { LAYER_META } from '../../types'
import { isAbortError } from '../../utils/request'

interface Props {
  selectedDate: string
  startDate?: string
  endDate?: string
  activeLayers: IntelLayer[]
  focusEventId?: string
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}

const SEVERITY: Record<string, { color: string; label: string }> = {
  critical: { color: '#f87171', label: '严重' },
  high: { color: '#fb923c', label: '高' },
  medium: { color: '#fbbf24', label: '中' },
  low: { color: '#a3a3a3', label: '低' },
  normal: { color: '#34d399', label: '正常' },
  watch: { color: '#fbbf24', label: '观察' },
}

function confidenceColor(level: string) {
  if (level === 'L1') return 'var(--success)'
  if (level === 'L2') return 'var(--accent)'
  if (level === 'L3') return 'var(--warning)'
  return 'var(--danger)'
}

export default function WarningIndicatorsView({ selectedDate, startDate = '', endDate = '', activeLayers, focusEventId, onAddToBrief }: Props) {
  const [data, setData] = useState<WarningIndicatorResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const requestGenerationRef = useRef(0)

  const date = startDate || endDate ? '' : selectedDate
  const layersKey = activeLayers.join(',')

  useEffect(() => {
    const requestGeneration = ++requestGenerationRef.current
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetchWarningIndicators({ date, startDate, endDate, layers: activeLayers }, controller.signal)
      .then(d => {
        if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) return
        setData(d)
        setLoading(false)
      })
      .catch(e => {
        if (isAbortError(e) || requestGeneration !== requestGenerationRef.current) return
        setError(e instanceof Error ? e.message : '预警指标加载失败')
        setLoading(false)
      })
    return () => controller.abort()
  }, [date, startDate, endDate, layersKey])

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

  if (!data) return null

  const level = SEVERITY[data.overall_level] ?? SEVERITY.normal
  const focusedIndicators = focusEventId
    ? data.indicators.filter(indicator => indicator.related_event_ids.includes(focusEventId))
    : data.indicators
  const visibleIndicators = focusEventId && focusedIndicators.length > 0 ? focusedIndicators : data.indicators

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{
        padding: '12px 14px', background: `${level.color}10`,
        border: `1px solid ${level.color}25`, borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <WarningCircle size={15} weight="duotone" color={level.color} />
          <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 700 }}>
            预警级别：{level.label}
          </span>
          <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {data.total_items} 条 · {data.active_indicator_count} 个指标
          </span>
        </div>
        {focusEventId && (
          <div style={{ fontSize: 9, color: 'var(--accent)', fontFamily: 'var(--font-mono)', marginBottom: 4 }}>
            聚焦事件：{focusEventId}{focusedIndicators.length === 0 ? ' · 暂无直接关联指标，显示全局指标' : ''}
          </div>
        )}
        <div style={{ fontSize: 10, lineHeight: 1.6, color: 'var(--text-tertiary)' }}>{data.methodology}</div>
      </div>

      <section>
        <SectionTitle title="触发指标" />
        <div style={{ display: 'grid', gap: 8 }}>
          {visibleIndicators.length === 0 && (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30, background: 'var(--bg-deep)', borderRadius: 'var(--radius-md)' }}>
              当前范围未触发预警指标。
            </div>
          )}
          {visibleIndicators.map((indicator, i) => (
            <IndicatorCard key={indicator.id} indicator={indicator} index={i} onAddToBrief={onAddToBrief} />
          ))}
        </div>
      </section>

      <section>
        <SectionTitle title="采集需求" />
        <div style={{ display: 'grid', gap: 6 }}>
          {data.collection_requirements.length === 0 && (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 10, padding: '8px 10px', background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)' }}>
              当前预警未生成额外采集需求。
            </div>
          )}
          {data.collection_requirements.map((task, i) => (
            <div key={`${task.task}-${i}`} style={{
              padding: '8px 10px', borderRadius: 'var(--radius-sm)',
              background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.22)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <Target size={12} weight="duotone" color="var(--accent)" />
                <span style={{ fontSize: 10, color: 'var(--text-primary)', fontWeight: 700 }}>{task.task}</span>
                <span style={{ marginLeft: 'auto', fontSize: 8, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{task.priority}</span>
              </div>
              <div style={{ fontSize: 9, lineHeight: 1.5, color: 'var(--text-tertiary)' }}>{task.rationale}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function IndicatorCard({
  indicator,
  index,
  onAddToBrief,
}: {
  indicator: WarningIndicator
  index: number
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}) {
  const severity = SEVERITY[indicator.severity] ?? SEVERITY.medium
  const confidence = confidenceColor(indicator.confidence.level)
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      style={{
        padding: '12px 14px', borderRadius: 'var(--radius-md)',
        background: 'rgba(32,36,40,0.72)', border: `1px solid ${severity.color}28`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9 }}>
        {indicator.status === 'triggered'
          ? <WarningCircle size={16} weight="duotone" color={severity.color} style={{ flexShrink: 0, marginTop: 1 }} />
          : <CheckCircle size={16} weight="duotone" color={severity.color} style={{ flexShrink: 0, marginTop: 1 }} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
            <span style={{ fontSize: 8, color: severity.color, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{indicator.id} {severity.label}</span>
            <span style={{ fontSize: 8, color: confidence, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
              {indicator.confidence.level} {indicator.confidence.label}
            </span>
            <span style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{indicator.review_window}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 5 }}>{indicator.title}</div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 5 }}>{indicator.trigger}</div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.55 }}>{indicator.rationale}</div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
            {indicator.layers.map(layer => {
              const meta = LAYER_META[layer as IntelLayer]
              return (
                <span key={layer} style={{
                  fontSize: 8, color: meta?.color ?? 'var(--text-secondary)', fontFamily: 'var(--font-mono)',
                  padding: '2px 6px', background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
                }}>
                  {meta?.label ?? layer}
                </span>
              )
            })}
            {indicator.countries.map(country => (
              <span key={country} style={{
                fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
                padding: '2px 6px', background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
              }}>
                {country}
              </span>
            ))}
          </div>

          {indicator.next_steps.length > 0 && (
            <div style={{ display: 'grid', gap: 3, marginTop: 8 }}>
              {indicator.next_steps.map((step, i) => (
                <div key={`${step}-${i}`} style={{ fontSize: 9, color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                  {i + 1}. {step}
                </div>
              ))}
            </div>
          )}
          {onAddToBrief && (
            <button
              onClick={() => onAddToBrief(warningToMaterial(indicator))}
              style={{
                marginTop: 8,
                display: 'inline-flex',
                alignItems: 'center',
                padding: '5px 8px',
                border: `1px solid ${severity.color}32`,
                borderRadius: 'var(--radius-sm)',
                background: `${severity.color}10`,
                color: severity.color,
                cursor: 'pointer',
                fontSize: 9,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
              }}
            >
              将预警加入简报
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function warningToMaterial(indicator: WarningIndicator): BriefWorkspaceMaterial {
  return {
    id: indicator.id,
    type: 'warning',
    title: indicator.title,
    summary: [indicator.trigger, indicator.rationale, ...indicator.next_steps].filter(Boolean).join('\n'),
    date: indicator.review_window,
    layer: indicator.layers.join(','),
    country: indicator.countries.join(','),
    confidence_level: `${indicator.confidence.level} ${indicator.confidence.label}`,
    origin: '预警指标',
  }
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)' }}>
      {title}
    </div>
  )
}
