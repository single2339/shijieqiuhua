import { useState } from 'react'
import { motion } from 'framer-motion'
import { X, MapPin, Clock, Code, FileText, Info, LinkSimple, ChartBar } from '@phosphor-icons/react'
import type { IntelItem } from '../types'
import { LAYER_META } from '../types'
import type { ItemAnalysisContext } from '../utils/intelDisplay'
import { useFloatingPanel } from '../hooks/useFloatingPanel'
import { safeExternalUrl } from '../utils/safeUrl'
import {
  confidenceColor,
  itemDisposition,
  itemConfidenceLevel,
  sourceCount,
  warningColor,
  warningLabel,
} from '../utils/intelDisplay'

interface Props {
  item: IntelItem
  onClose: () => void
  isMobile?: boolean
  analysisContext?: ItemAnalysisContext
  onAnalyzeItem?: () => void
  onAddToBrief?: () => void
}

function VerdictBadge({ verdict }: { verdict: IntelItem['verdict'] }) {
  const cfg = {
    verified: { color: 'var(--success)', bg: 'rgba(79,188,141,0.10)', label: '已核实' },
    false: { color: 'var(--danger)', bg: 'rgba(217,107,98,0.10)', label: '虚假' },
    uncertain: { color: 'var(--warning)', bg: 'rgba(212,160,72,0.10)', label: '不确定' },
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

function toneAlpha(tone: string, alpha: number): string {
  const varColors: Record<string, [number, number, number]> = {
    'var(--success)': [79, 188, 141],
    'var(--accent)': [200, 164, 93],
    'var(--warning)': [212, 160, 72],
    'var(--danger)': [217, 107, 98],
    'var(--info)': [110, 166, 184],
    'var(--text-secondary)': [183, 173, 156],
    'var(--text-tertiary)': [127, 118, 105],
  }
  const rgb = varColors[tone]
  if (rgb) return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`
  if (/^#[0-9a-fA-F]{6}$/.test(tone)) {
    const r = parseInt(tone.slice(1, 3), 16)
    const g = parseInt(tone.slice(3, 5), 16)
    const b = parseInt(tone.slice(5, 7), 16)
    return `rgba(${r},${g},${b},${alpha})`
  }
  return `rgba(156,143,130,${alpha})`
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
            style={{ position: 'fixed', inset: 0, zIndex: 'var(--z-intel-card)' }}
          />
          <div style={{
            position: 'absolute', bottom: '120%', left: 0, zIndex: 'var(--z-intel-tooltip)',
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

function AnalysisMetric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div style={{
      padding: '7px 9px',
      background: 'var(--bg-deep)',
      border: `1px solid ${toneAlpha(tone, 0.14)}`,
      borderRadius: 'var(--radius-sm)',
      minWidth: 0,
    }}>
      <div style={{
        fontSize: 8, color: 'var(--text-tertiary)',
        fontFamily: 'var(--font-mono)', marginBottom: 3,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 10, color: tone, fontFamily: 'var(--font-mono)',
        fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {value}
      </div>
    </div>
  )
}

function AnalystDispositionPanel({
  label,
  rationale,
  tone,
}: {
  label: string
  rationale: string
  tone: string
}) {
  return (
    <div style={{
      marginTop: 10,
      padding: '9px 10px',
      background: toneAlpha(tone, 0.08),
      border: `1px solid ${toneAlpha(tone, 0.18)}`,
      borderRadius: 'var(--radius-sm)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 8, marginBottom: 4,
      }}>
        <span style={{ fontSize: 9, color: tone, fontFamily: 'var(--font-mono)', fontWeight: 800, letterSpacing: 0.5 }}>
          分析师处置
        </span>
        <span style={{
          color: tone, background: toneAlpha(tone, 0.08),
          border: `1px solid ${toneAlpha(tone, 0.2)}`,
          borderRadius: 'var(--radius-sm)',
          padding: '2px 8px',
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          fontWeight: 800,
        }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        {rationale}
      </div>
    </div>
  )
}

function WorkupSection({ title, items, tone }: { title: string; items: string[]; tone?: string }) {
  return (
    <div style={{
      padding: '9px 10px',
      background: 'var(--bg-deep)',
      border: '1px solid var(--glass-border)',
      borderRadius: 'var(--radius-sm)',
    }}>
      <div style={{
        fontSize: 8, color: tone || 'var(--text-tertiary)',
        fontFamily: 'var(--font-mono)', fontWeight: 800,
        letterSpacing: 0.7, marginBottom: 6,
      }}>
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {items.map((text, i) => (
          <div key={`${title}-${i}`} style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
            <span style={{
              width: 4, height: 4, borderRadius: '50%',
              background: tone || 'var(--text-tertiary)',
              marginTop: 6, flexShrink: 0,
            }} />
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              {text}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function EvidenceChainPanel({ item, analysisContext }: { item: IntelItem; analysisContext?: ItemAnalysisContext }) {
  const sources = [...new Set([item.source_system, ...(item.sources ?? [])].filter(Boolean))]
  const independentCount = analysisContext?.eventSourceCount ?? sources.length
  const replicationStatus = independentCount >= 3
    ? '三方交叉支撑'
    : independentCount === 2
      ? '双源支撑'
      : '单源线索'

  return (
    <div style={{
      marginTop: 10, padding: '9px 10px',
      background: 'var(--bg-deep)',
      border: '1px solid var(--glass-border)',
      borderRadius: 'var(--radius-sm)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 8, marginBottom: 8,
      }}>
        <div style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontWeight: 800, letterSpacing: 0.7 }}>
          证据链
        </div>
        <div style={{ fontSize: 9, color: independentCount >= 2 ? 'var(--accent)' : 'var(--warning)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
          {replicationStatus}
        </div>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
        gap: 6,
        marginBottom: 8,
      }}>
        <AnalysisMetric label="独立来源" value={`${independentCount} 源`} tone={independentCount >= 2 ? 'var(--success)' : 'var(--warning)'} />
        <AnalysisMetric label="事件簇" value={analysisContext?.eventId || '未入簇'} tone={analysisContext?.eventId ? 'var(--accent)' : 'var(--text-tertiary)'} />
        <AnalysisMetric label="原始证据" value={`#${item.evidence_count}`} tone="var(--text-secondary)" />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
        {sources.slice(0, 6).map(source => (
          <span key={source} style={{
            padding: '2px 7px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            maxWidth: 150,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {source}
          </span>
        ))}
        {sources.length > 6 && (
          <span style={{ color: 'var(--text-tertiary)', fontSize: 9, fontFamily: 'var(--font-mono)' }}>
            +{sources.length - 6}
          </span>
        )}
      </div>
      <div style={{ marginTop: 7, fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.45 }}>
        {independentCount < 3
          ? '需继续排查同源转载与引用链，补足第三方独立来源后再提升等级。'
          : '来源数满足三方验证门槛，仍需保留原文链接与反证检查。'}
      </div>
    </div>
  )
}

function IntelligenceGradePanel({
  level,
  label,
  rationale,
  eventStatus,
  eventSourceCount,
}: {
  level: string
  label: string
  rationale: string
  eventStatus?: string
  eventSourceCount?: number
}) {
  const tone = confidenceColor(level)
  return (
    <div style={{
      marginTop: 10,
      padding: '9px 10px',
      background: toneAlpha(tone, 0.07),
      border: `1px solid ${toneAlpha(tone, 0.16)}`,
      borderRadius: 'var(--radius-sm)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 9, color: tone, fontFamily: 'var(--font-mono)', fontWeight: 800 }}>
          情报等级 {level} {label}
        </span>
        {eventStatus && (
          <span style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {eventStatus}
          </span>
        )}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        {eventSourceCount ? `${eventSourceCount} 个事件级来源支撑。` : rationale}
      </div>
    </div>
  )
}

export default function IntelCard({ item, onClose, isMobile, analysisContext, onAnalyzeItem, onAddToBrief }: Props) {
  const meta = LAYER_META[item.layer]
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const floating = useFloatingPanel({
    enabled: !isMobile,
    width: 400,
    height: 500,
    anchor: 'bottom-center',
  })
  const longSummary = item.summary.length > 120
  const itemLevel = itemConfidenceLevel(item)
  const displayedLevel = analysisContext?.eventConfidenceLevel ?? itemLevel.level
  const displayedLabel = analysisContext?.eventConfidenceLabel ?? itemLevel.label
  const displayedRationale = analysisContext?.eventConfidenceLevel
    ? '来自事件核查结果。'
    : itemLevel.rationale
  const disposition = itemDisposition(item, analysisContext)
  const independentSources = analysisContext?.eventSourceCount ?? sourceCount(item)
  const capturedDate = item.captured_at?.slice(0, 10) || '未知时间'
  const itemUrl = safeExternalUrl(item.url)
  const factItems = [
    `${item.source_system || '未知来源'} 于 ${capturedDate} 捕获该条情报。`,
    `地理标注为 ${item.location_name} · ${item.country}。`,
    analysisContext?.eventId
      ? `已归入事件簇 ${analysisContext.eventId}，事件级状态为 ${analysisContext.eventVerificationStatus || '待判定'}。`
      : '尚未归入事件簇，当前仍按单条线索处理。',
  ]
  const assessmentItems = [
    `当前情报等级为 ${displayedLevel} ${displayedLabel}：${displayedRationale}`,
    independentSources >= 3
      ? '来源数量达到三方验证门槛，可作为进一步研判的稳定证据。'
      : `当前只有 ${independentSources} 个独立来源支撑，需要补充外部交叉验证。`,
    analysisContext?.warningTitle
      ? `已关联预警指标：${analysisContext.warningTitle}`
      : '暂未触发高优先级预警指标。',
  ]
  const pendingItems = [
    ...(independentSources < 3 ? ['补充至至少 3 个独立来源，并区分原创报道、转载和引用链。'] : []),
    ...(item.verdict !== 'verified' ? ['复核原文、发布时间、作者/机构身份与关键数字。'] : []),
    ...(!analysisContext?.eventId ? ['与同主题情报进行事件聚类，确认是否属于更大态势。'] : []),
    '主动寻找反证或替代解释，避免只沿当前叙事继续确认。',
  ]

  return (
    <motion.div
      initial={{ y: 20, opacity: 0, scale: 0.96 }}
      animate={{ y: 0, opacity: 1, scale: 1 }}
      exit={{ y: 20, opacity: 0, scale: 0.96 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      className={isMobile ? 'glass-panel mobile-bottom-sheet' : 'glass-panel'}
      style={{
        position: 'fixed',
        bottom: isMobile ? 0 : 16,
        left: isMobile ? 0 : '50%',
        transform: isMobile ? 'none' : 'translateX(-50%)',
        width: isMobile ? '100%' : 400,
        maxWidth: isMobile ? '100%' : '92vw',
        height: isMobile ? undefined : 'min(500px, 66vh)',
        maxHeight: isMobile ? '78vh' : '66vh',
        overflowY: 'auto',
        borderRadius: isMobile ? 'var(--radius-lg) var(--radius-lg) 0 0' : 'var(--radius-lg)',
        padding: isMobile ? 12 : 12, zIndex: 'var(--z-panel)',
        border: `1px solid ${meta.color}26`,
        boxShadow: 'var(--glass-inner-shadow), var(--shadow-diffuse)',
        fontFamily: 'var(--font-ui)',
        ...floating.panelStyle,
      }}
    >
      {/* Top row */}
      <div {...floating.dragHandleProps} style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        margin: -12,
        marginBottom: 0,
        padding: 12,
        borderBottom: '1px solid var(--glass-border)',
        ...floating.dragHandleStyle,
      }}>
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
                boxShadow: `0 0 4px ${meta.color}44`,
              }} />
              {meta.label.toUpperCase()}
            </span>
            <VerdictBadge verdict={item.verdict} />
            <span style={{
              background: toneAlpha(confidenceColor(displayedLevel), 0.08),
              color: confidenceColor(displayedLevel),
              padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: 9,
              fontWeight: 700, border: `1px solid ${toneAlpha(confidenceColor(displayedLevel), 0.18)}`,
              fontFamily: 'var(--font-mono)',
            }}>
              {displayedLevel} {displayedLabel}
            </span>
            <span style={{
              fontSize: 9, color: 'var(--text-tertiary)',
              fontFamily: 'var(--font-mono)',
            }}>
              #{item.evidence_count}
            </span>
            <span style={{
              background: toneAlpha(disposition.tone, 0.08),
              color: disposition.tone,
              padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: 9,
              fontWeight: 800, border: `1px solid ${toneAlpha(disposition.tone, 0.18)}`,
              fontFamily: 'var(--font-mono)',
            }}>
              {disposition.label}
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

      <IntelligenceGradePanel
        level={displayedLevel}
        label={displayedLabel}
        rationale={displayedRationale}
        eventStatus={analysisContext?.eventVerificationStatus}
        eventSourceCount={analysisContext?.eventSourceCount}
      />

      <AnalystDispositionPanel
        label={disposition.label}
        rationale={disposition.rationale}
        tone={disposition.tone}
      />

      {/* Core claim */}
      <div style={{
        marginTop: 10, padding: '9px 10px',
        background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
        borderRadius: 'var(--radius-sm)',
      }}>
        <div style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontWeight: 800, marginBottom: 5 }}>
          核心声明
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.5 }}>
          {item.title}
        </div>
      </div>

      {/* Fact / assessment / verification workup */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',
        gap: 8,
        marginTop: 10,
      }}>
        <WorkupSection title="确认事实" items={factItems} tone="var(--accent)" />
        <WorkupSection title="分析判断" items={assessmentItems} tone={confidenceColor(displayedLevel)} />
      </div>
      <div style={{ marginTop: 8 }}>
        <WorkupSection title="待核查问题" items={pendingItems} tone={disposition.tone} />
      </div>

      {/* Analysis linkage */}
      {analysisContext?.eventTitle && (
        <div style={{
          marginTop: 8, padding: '8px 10px',
          background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
          borderRadius: 'var(--radius-sm)',
        }}>
          <div style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginBottom: 3 }}>
            关联事件
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {analysisContext.eventTitle}
          </div>
        </div>
      )}

      {analysisContext?.warningTitle && (
        <div style={{
          marginTop: 8, padding: '8px 10px',
          background: toneAlpha(warningColor(analysisContext.warningSeverity), 0.08),
          border: `1px solid ${toneAlpha(warningColor(analysisContext.warningSeverity), 0.16)}`,
          borderRadius: 'var(--radius-sm)',
        }}>
          <div style={{ fontSize: 8, color: warningColor(analysisContext.warningSeverity), fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: 3 }}>
            {analysisContext.warningId} · {warningLabel(analysisContext.warningSeverity)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {analysisContext.warningTitle}
          </div>
        </div>
      )}

      <EvidenceChainPanel item={item} analysisContext={analysisContext} />

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

      {(onAnalyzeItem || onAddToBrief) && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: onAnalyzeItem && onAddToBrief ? '1fr 1fr' : '1fr',
          gap: 8,
          marginTop: 10,
        }}>
          {onAnalyzeItem && (
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={onAnalyzeItem}
              className="interactive-btn"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                padding: '7px 10px',
                border: '1px solid rgba(200,164,93,0.24)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--accent-dim)',
                color: 'var(--accent)',
                cursor: 'pointer',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
              }}
            >
              <ChartBar size={12} weight="duotone" />
              按此情报分析
            </motion.button>
          )}
          {onAddToBrief && (
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={onAddToBrief}
              className="interactive-btn"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                padding: '7px 10px',
                border: '1px solid var(--glass-border)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-deep)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
              }}
            >
              <FileText size={12} weight="duotone" />
              加入简报候选
            </motion.button>
          )}
        </div>
      )}

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
        <span style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-tertiary)' }}>
          {itemUrl && (
            <a
              href={itemUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                color: 'var(--accent)', textDecoration: 'none',
              }}
            >
              <LinkSimple size={10} weight="duotone" />
              原文
            </a>
          )}
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
