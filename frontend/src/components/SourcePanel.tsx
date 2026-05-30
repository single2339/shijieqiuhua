import { motion, AnimatePresence } from 'framer-motion'
import { CaretRight, X } from '@phosphor-icons/react'
import type { SourceInfo } from '../types'

interface Props { sources: SourceInfo[]; expanded: boolean; onToggle: () => void; isMobile?: boolean }

function credColor(v: number): string {
  if (v >= 0.85) return 'var(--success)'
  if (v >= 0.7) return 'var(--warning)'
  return 'var(--danger)'
}

export default function SourcePanel({ sources, expanded, onToggle, isMobile }: Props) {
  if (!sources.length) return null

  if (isMobile) {
    return (
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            className="glass-panel mobile-full-panel"
            style={{
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px 18px 10px', borderBottom: '1px solid var(--glass-border)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent)' }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', letterSpacing: 1 }}>
                  情报来源
                </span>
              </div>
              <motion.button
                whileTap={{ scale: 0.9 }}
                onClick={onToggle}
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
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
              {sources.map((s, i) => (
                <motion.div
                  key={s.name}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  style={{ padding: '8px 18px', borderBottom: '1px solid var(--border-subtle)' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, fontFamily: 'var(--font-ui)' }}>
                      {s.name}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)', color: credColor(s.credibility) }}>
                      {Math.round(s.credibility * 100)}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ flex: 1, height: 4, background: 'var(--bg-deep)', borderRadius: 2, overflow: 'hidden' }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.round(s.credibility * 100)}%` }}
                        transition={{ delay: i * 0.03, duration: 0.4 }}
                        style={{ height: '100%', background: credColor(s.credibility), borderRadius: 2 }}
                      />
                    </div>
                    <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                      {s.document_count}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    )
  }

  return (
    <>
      <motion.button
        initial={{ x: 0 }}
        animate={{ x: expanded ? -212 : 0 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        onClick={onToggle}
        className="interactive-btn"
        style={{
          position: 'fixed', right: expanded ? 212 : 0, top: '50%', transform: 'translateY(-50%)',
          width: 22, height: 60,
          background: 'var(--glass-bg)',
          border: '1px solid var(--glass-border)',
          borderRight: 'none', borderRadius: 'var(--radius-sm) 0 0 var(--radius-sm)',
          cursor: 'pointer', zIndex: 'var(--z-layer-panel)', color: 'var(--text-tertiary)',
          fontSize: 9, writingMode: 'vertical-rl', letterSpacing: 2,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 4,
          boxShadow: 'var(--shadow-diffuse)',
        }}
      >
        <CaretRight size={10} weight="bold" style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
        SOURCES ({sources.length})
      </motion.button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ x: 212 }}
            animate={{ x: 0 }}
            exit={{ x: 212 }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
            className="glass-panel"
            style={{
              position: 'fixed', right: 0, top: 44,
              width: 212, height: 'calc(100% - 44px)',
              borderLeft: '1px solid var(--glass-border)',
              borderTop: 'none', borderBottom: 'none', borderRight: 'none',
              borderRadius: 0,
              zIndex: 'var(--z-source-panel)',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div style={{
              padding: '10px 14px 8px',
              fontSize: 9, fontWeight: 700, letterSpacing: 2,
              color: 'var(--text-secondary)', borderBottom: '1px solid var(--glass-border)',
              fontFamily: 'var(--font-mono)',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent)' }} />
              情报来源
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
              {sources.map((s, i) => (
                <motion.div
                  key={s.name}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  style={{
                    padding: '6px 14px',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{
                      fontSize: 10, color: 'var(--text-primary)', fontWeight: 500,
                      maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', fontFamily: 'var(--font-ui)',
                    }}>
                      {s.name}
                    </span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: credColor(s.credibility),
                    }}>
                      {Math.round(s.credibility * 100)}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      flex: 1, height: 2, background: 'var(--bg-deep)', borderRadius: 1,
                      overflow: 'hidden',
                    }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.round(s.credibility * 100)}%` }}
                        transition={{ delay: i * 0.03, duration: 0.4 }}
                        style={{
                          height: '100%',
                          background: credColor(s.credibility), borderRadius: 1,
                        }}
                      />
                    </div>
                    <span style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                      {s.document_count}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
