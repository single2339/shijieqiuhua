import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import type { IntelItem } from '../types'
import { LAYER_META } from '../types'
import type { ItemAnalysisContext } from '../utils/intelDisplay'
import { confidenceColor, itemConfidenceLevel, warningColor, warningLabel } from '../utils/intelDisplay'

interface Props {
  items: IntelItem[]
  onSelect: (item: IntelItem) => void
  selectedId: string | null
  hasMore?: boolean
  loadingMore?: boolean
  onLoadMore?: () => void
  contextByItemId?: Record<string, ItemAnalysisContext>
}

function layerLabel(l: IntelItem['layer']) {
  return LAYER_META[l].label
}

export default function MessageFeed({ items, onSelect, selectedId, hasMore, loadingMore, onLoadMore, contextByItemId = {} }: Props) {
  const sentinelRef = useRef<HTMLDivElement>(null)
  const onLoadMoreRef = useRef(onLoadMore)
  onLoadMoreRef.current = onLoadMore

  useEffect(() => {
    if (!onLoadMore || !hasMore) return
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) onLoadMoreRef.current?.() },
      { rootMargin: '100px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [onLoadMore, hasMore])
  if (!items.length) return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100%', color: 'var(--text-tertiary)', fontSize: 11,
      fontFamily: 'var(--font-mono)', letterSpacing: 1, gap: 8,
    }}>
      <span style={{
        width: 34, height: 34, borderRadius: '50%',
        border: '1px solid var(--border-active)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--accent)', fontSize: 9,
      }}>
        NIL
      </span>
      当前筛选条件下暂无情报
    </div>
  )

  return (
    <div style={{ height: '100%', overflowY: 'auto' }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 'var(--z-map-controls)',
        background: 'rgba(18,20,22,0.92)', backdropFilter: 'blur(18px)',
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '8px 14px', borderBottom: '1px solid var(--glass-border)',
        fontFamily: 'var(--font-mono)', fontSize: 9,
        color: 'var(--text-secondary)', letterSpacing: 1,
      }}>
        <span>INTELLIGENCE QUEUE</span>
        <span style={{ color: 'var(--accent)' }}>{items.length} ITEMS</span>
      </div>
      <div style={{ padding: '2px 0' }}>
        {items.map((item, i) => {
          const meta = LAYER_META[item.layer]
          const ctx = contextByItemId[item.id]
          const confidence = ctx?.eventConfidenceLevel
            ? { level: ctx.eventConfidenceLevel, label: ctx.eventConfidenceLabel ?? '' }
            : itemConfidenceLevel(item)
          const isSelected = item.id === selectedId
          const warnColor = warningColor(ctx?.warningSeverity)
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: (i % 50) * 0.008, duration: 0.2 }}
              onClick={() => onSelect(item)}
              className="msg-feed-item"
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 12px', cursor: 'pointer',
                background: isSelected ? `${meta.color}08` : 'transparent',
                borderLeft: `2px solid ${isSelected ? meta.color : 'transparent'}`,
                borderBottom: '1px solid var(--border-subtle)',
              }}
              data-selected={isSelected}
            >
              <span style={{ width: 3, height: 34, borderRadius: 2, background: ctx?.warningSeverity ? warnColor : meta.color, flexShrink: 0 }} />
              <span style={{
                width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
                background: confidenceColor(confidence.level),
              }} />
              <span style={{ fontSize: 9, fontWeight: 700, color: meta.color, minWidth: 20, fontFamily: 'var(--font-mono)' }}>
                {layerLabel(item.layer)}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{
                  display: 'block', fontSize: 11, color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  fontFamily: 'var(--font-ui)',
                  letterSpacing: 0.1,
                }}>
                  {item.title}
                </span>
                {(ctx?.eventId || ctx?.warningSeverity) && (
                  <span style={{
                    display: 'block', marginTop: 1, fontSize: 8, color: 'var(--text-tertiary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {ctx?.eventId ? `${ctx.eventId} · ${ctx.eventVerificationStatus}` : ''}
                    {ctx?.eventId && ctx?.warningSeverity ? ' · ' : ''}
                    {ctx?.warningSeverity ? warningLabel(ctx.warningSeverity) : ''}
                  </span>
                )}
              </span>
              <span style={{
                fontSize: 9, fontWeight: 600, fontFamily: 'var(--font-mono)',
                color: confidenceColor(confidence.level),
                minWidth: 30, textAlign: 'right',
              }}>
                {confidence.level}
              </span>
              <span style={{
                fontSize: 9, color: 'var(--text-tertiary)', minWidth: 50,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                textAlign: 'right',
              }}>
                {item.country}
              </span>
              <span style={{
                fontSize: 8, color: 'var(--text-tertiary)', minWidth: 36,
                textAlign: 'right', fontFamily: 'var(--font-mono)',
              }}>
                {item.source_system}
                {item.sources.length > 1 && (
                  <span style={{ color: 'var(--accent)', marginLeft: 2 }}>+{item.sources.length - 1}</span>
                )}
              </span>
            </motion.div>
          )
        })}
        <div ref={sentinelRef} style={{ height: 1 }} />
        {loadingMore && (
          <div style={{ textAlign: 'center', padding: '8px 0', color: 'var(--text-tertiary)', fontSize: 10, fontFamily: 'var(--font-mono)' }}>
            正在加载后续情报...
          </div>
        )}
        {!hasMore && items.length > 0 && (
          <div style={{ textAlign: 'center', padding: '8px 0', color: 'var(--text-tertiary)', fontSize: 9, fontFamily: 'var(--font-mono)', opacity: 0.5 }}>
            全部 {items.length} 条
          </div>
        )}
      </div>
    </div>
  )
}
