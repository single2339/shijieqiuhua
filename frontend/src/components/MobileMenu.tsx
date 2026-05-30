import { motion, AnimatePresence } from 'framer-motion'
import { MagnifyingGlass, ChartBar, FileText, Brain, Rows, Database, X } from '@phosphor-icons/react'

function menuBtnStyle(accentColor?: string): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 8,
    width: '100%', padding: '8px 12px',
    background: 'rgba(0,0,0,0.02)',
    border: accentColor ? `1px solid ${accentColor}22` : '1px solid var(--glass-border)',
    borderRadius: 'var(--radius-sm)',
    color: accentColor || 'var(--text-secondary)',
    fontSize: 12, fontFamily: 'var(--font-mono)', cursor: 'pointer',
    textAlign: 'left' as const,
  }
}

interface Props {
  show: boolean
  onClose: () => void
  onOpenPanel: (panel: string) => void
  onOpenSources: () => void
  triggerCollect: () => void
  collecting: boolean
  totalItems: number
  sourcesCount: number
  liveClock: React.ReactNode
}

export default function MobileMenu({
  show, onClose, onOpenPanel, onOpenSources,
  triggerCollect, collecting, totalItems, sourcesCount, liveClock,
}: Props) {
  return (
    <AnimatePresence>
      {show && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mobile-menu-overlay"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
            className="mobile-menu-panel"
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)', letterSpacing: 2, fontFamily: 'var(--font-mono)' }}>
                菜单
              </span>
              <motion.button
                whileTap={{ scale: 0.9 }}
                onClick={onClose}
                style={{
                  background: 'rgba(0,0,0,0.04)', border: '1px solid var(--glass-border)',
                  color: 'var(--text-tertiary)', cursor: 'pointer',
                  width: 32, height: 32, borderRadius: 'var(--radius-sm)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                <X size={14} weight="bold" />
              </motion.button>
            </div>

            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => onOpenPanel('ask')}
              style={menuBtnStyle('var(--accent)')}
            >
              <MagnifyingGlass size={16} weight="duotone" color="var(--accent)" />
              向AI分析师提问
            </motion.button>

            <div style={{ height: 1, background: 'var(--border-subtle)', margin: '4px 0' }} />

            {[
              { icon: <ChartBar size={16} weight="duotone" />, label: '情报看板', onClick: () => onOpenPanel('stats') },
              { icon: <FileText size={16} weight="duotone" />, label: '态势简报', onClick: () => onOpenPanel('report') },
              { icon: <Brain size={16} weight="duotone" />, label: '超级分析', onClick: () => onOpenPanel('super') },
              { icon: <ChartBar size={16} weight="duotone" />, label: '情报分析', onClick: () => onOpenPanel('analysis') },
              { icon: <Rows size={16} weight="duotone" />, label: '情报来源', onClick: onOpenSources },
            ].map(item => (
              <motion.button
                key={item.label}
                whileTap={{ scale: 0.98 }}
                onClick={item.onClick}
                style={menuBtnStyle()}
              >
                {item.icon}
                {item.label}
              </motion.button>
            ))}

            <div style={{ height: 1, background: 'var(--border-subtle)', margin: '4px 0' }} />

            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => { onClose(); triggerCollect() }}
              disabled={collecting}
              style={menuBtnStyle(collecting ? undefined : 'var(--accent)')}
            >
              <Database size={16} weight="duotone" color={collecting ? undefined : 'var(--accent)'} />
              {collecting ? '采集中...' : '+ 启动采集'}
            </motion.button>

            <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginBottom: 4 }}>
                全球情报指挥系统
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                情报 {totalItems} · 来源 {sourcesCount}
              </div>
              <div style={{ marginTop: 8, fontSize: 10 }}>
                {liveClock}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
