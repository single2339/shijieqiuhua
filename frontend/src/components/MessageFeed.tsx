import { motion } from 'framer-motion'
import type { IntelItem } from '../types'
import { LAYER_META } from '../types'

interface Props {
  items: IntelItem[]
  onSelect: (item: IntelItem) => void
  selectedId: string | null
}

function layerLabel(l: IntelItem['layer']) {
  return LAYER_META[l].label
}

export default function MessageFeed({ items, onSelect, selectedId }: Props) {
  if (!items.length) return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100%', color: 'var(--text-tertiary)', fontSize: 11,
      fontFamily: 'var(--font-mono)', letterSpacing: 1, gap: 8,
    }}>
      <span style={{ fontSize: 24, opacity: 0.3 }}>◌</span>
      暂无匹配的情报数据
    </div>
  )

  return (
    <div style={{ height: '100%', overflowY: 'auto' }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 10, background: 'var(--bg-surface)',
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '6px 14px', borderBottom: '1px solid var(--glass-border)',
        fontFamily: 'var(--font-mono)', fontSize: 9,
        color: 'var(--text-secondary)', letterSpacing: 1,
      }}>
        <span>情报消息流</span>
        <span style={{ color: 'var(--accent)' }}>{items.length} 条</span>
      </div>
      <div style={{ padding: '2px 0' }}>
        {items.map((item, i) => {
          const meta = LAYER_META[item.layer]
          const pct = Math.round(item.confidence * 100)
          const isSelected = item.id === selectedId
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.008, duration: 0.2 }}
              onClick={() => onSelect(item)}
              className="msg-feed-item"
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '5px 12px', cursor: 'pointer',
                background: isSelected ? `${meta.color}08` : 'transparent',
                borderLeft: `2px solid ${isSelected ? meta.color : 'transparent'}`,
              }}
              data-selected={isSelected}
            >
              <span style={{ width: 3, height: 24, borderRadius: 2, background: meta.color, flexShrink: 0 }} />
              <span style={{
                width: 4, height: 4, borderRadius: '50%', flexShrink: 0,
                background: pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)',
              }} />
              <span style={{ fontSize: 9, fontWeight: 700, color: meta.color, minWidth: 20, fontFamily: 'var(--font-mono)' }}>
                {layerLabel(item.layer)}
              </span>
              <span style={{
                flex: 1, fontSize: 11, color: 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                fontFamily: 'var(--font-ui)',
              }}>
                {item.title}
              </span>
              <span style={{
                fontSize: 9, fontWeight: 600, fontFamily: 'var(--font-mono)',
                color: pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)',
                minWidth: 40, textAlign: 'right',
              }}>
                {pct}%
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
      </div>
    </div>
  )
}
