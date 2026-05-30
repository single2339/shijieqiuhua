import { motion, AnimatePresence } from 'framer-motion'
import { Atom, Globe, ArrowUpRight } from '@phosphor-icons/react'
import type { SuperAnalysisResponse, BayesianIntelItem } from '../types'
import { PRIOR_LABELS, PRIOR_COLORS, VERDICT_COLORS } from '../lib/markdown'

interface Props {
  result: SuperAnalysisResponse
  expandedItem: number | null
  setExpandedItem: (idx: number | null) => void
  activeTab: 'intel' | 'web'
  setActiveTab: (tab: 'intel' | 'web') => void
}

const sidebarVariants = {
  hidden: { opacity: 0, x: 20 },
  visible: {
    opacity: 1, x: 0,
    transition: { type: 'spring' as const, stiffness: 80, damping: 18, delay: 0.08 },
  },
}

const itemStagger = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, x: -16 },
  visible: {
    opacity: 1, x: 0,
    transition: { type: 'spring' as const, stiffness: 100, damping: 18 },
  },
}

const breatheDot = {
  animate: {
    scale: [1, 1.35, 1],
    opacity: [0.7, 1, 0.7],
    transition: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' as const },
  },
}

export default function SuperAnalysisSidebar({
  result, expandedItem, setExpandedItem, activeTab, setActiveTab,
}: Props) {
  return (
    <motion.div
      variants={sidebarVariants}
      initial="hidden"
      animate="visible"
      style={{
        width: 340, flexShrink: 0,
        borderLeft: '1px solid var(--glass-border)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
        background: 'rgba(0,0,0,0.008)',
      }}
    >
      {/* Tabs */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--glass-border)',
        flexShrink: 0,
      }}>
        <button onClick={() => setActiveTab('intel')} style={{
          flex: 1, padding: '10px 0', fontSize: 10, fontWeight: 600,
          fontFamily: 'var(--font-mono)',
          border: 'none', cursor: 'pointer',
          background: activeTab === 'intel' ? 'rgba(13,148,136,0.03)' : 'transparent',
          color: activeTab === 'intel' ? 'var(--accent)' : 'var(--text-tertiary)',
          borderBottom: activeTab === 'intel'
            ? '2px solid var(--accent)' : '2px solid transparent',
          transition: 'color 0.2s, background 0.2s',
        }}>
          <Atom size={10} weight="duotone" />
          {' 相关情报'}
          <span style={{ marginLeft: 4, opacity: 0.45 }}>
            ({result.relevant_items.length})
          </span>
        </button>
        <button onClick={() => setActiveTab('web')} style={{
          flex: 1, padding: '10px 0', fontSize: 10, fontWeight: 600,
          fontFamily: 'var(--font-mono)',
          border: 'none', cursor: 'pointer',
          background: activeTab === 'web' ? 'rgba(13,148,136,0.03)' : 'transparent',
          color: activeTab === 'web' ? 'var(--accent)' : 'var(--text-tertiary)',
          borderBottom: activeTab === 'web'
            ? '2px solid var(--accent)' : '2px solid transparent',
          transition: 'color 0.2s, background 0.2s',
        }}>
          <Globe size={10} weight="duotone" />
          {' 网络数据'}
          <span style={{ marginLeft: 4, opacity: 0.45 }}>
            ({result.web_results.length})
          </span>
        </button>
      </div>

      {/* Intel items tab */}
      <AnimatePresence mode="wait">
        {activeTab === 'intel' && (
          <motion.div
            key="intel-tab"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}
          >
            {result.relevant_items.length === 0 ? (
              <div style={{
                textAlign: 'center', padding: 30,
                fontSize: 10, color: 'var(--text-tertiary)', opacity: 0.5,
              }}>
                {'无相关情报项'}
              </div>
            ) : (
              <motion.div
                variants={itemStagger}
                initial="hidden"
                animate="visible"
                style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
              >
                {result.relevant_items.slice(0, 15).map((item: BayesianIntelItem, idx: number) => {
                  const supportCount = item.evidence_items.filter(e => e.direction === 'support').length
                  const againstCount = item.evidence_items.filter(e => e.direction !== 'support').length
                  const isOpen = expandedItem === idx

                  return (
                    <motion.div
                      key={idx}
                      variants={itemVariants}
                      layout
                      whileHover={{ scale: 1.01 }}
                      whileTap={{ scale: 0.985 }}
                      style={{
                        padding: '10px 12px',
                        background: isOpen ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.4)',
                        borderRadius: 'var(--radius-md)',
                        border: isOpen
                          ? '1px solid rgba(13,148,136,0.12)'
                          : '1px solid var(--glass-border)',
                        cursor: 'pointer',
                        boxShadow: isOpen ? '0 2px 12px rgba(0,0,0,0.04)' : 'none',
                        transition: 'background 0.2s, border-color 0.2s, box-shadow 0.2s',
                      }}
                      onClick={() => setExpandedItem(isOpen ? null : idx)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <motion.span
                          variants={breatheDot}
                          animate="animate"
                          style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: VERDICT_COLORS[item.verdict] ?? 'var(--text-tertiary)',
                            flexShrink: 0,
                          }}
                        />
                        <span style={{
                          fontSize: 10, fontWeight: 500, color: 'var(--text-primary)',
                          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {item.title}
                        </span>
                        <span style={{
                          fontSize: 9, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: item.confidence >= 0.7 ? 'var(--success)'
                            : item.confidence >= 0.4 ? 'var(--warning)' : 'var(--danger)',
                          flexShrink: 0,
                        }}>
                          {(item.confidence * 100).toFixed(0)}%
                        </span>
                      </div>

                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        marginTop: 5, paddingLeft: 14,
                      }}>
                        <span style={{ fontSize: 8, color: 'var(--text-tertiary)' }}>{item.source}</span>
                        <span style={{ fontSize: 8, color: 'var(--text-tertiary)', opacity: 0.35 }}>{item.date}</span>
                        <span style={{
                          fontSize: 7, padding: '1px 6px', borderRadius: 3,
                          background: `${PRIOR_COLORS[item.prior_class] ?? '#6b7280'}12`,
                          color: PRIOR_COLORS[item.prior_class] ?? '#6b7280',
                          fontFamily: 'var(--font-mono)', fontWeight: 600,
                          marginLeft: 'auto',
                        }}>
                          {PRIOR_LABELS[item.prior_class] ?? item.prior_class}
                        </span>
                      </div>

                      {(supportCount > 0 || againstCount > 0) && (
                        <div style={{ display: 'flex', gap: 8, marginTop: 4, paddingLeft: 14 }}>
                          {supportCount > 0 && (
                            <span style={{ fontSize: 8, color: 'var(--success)', fontFamily: 'var(--font-mono)', opacity: 0.55 }}>
                              +{supportCount} {'支持'}
                            </span>
                          )}
                          {againstCount > 0 && (
                            <span style={{ fontSize: 8, color: 'var(--danger)', fontFamily: 'var(--font-mono)', opacity: 0.55 }}>
                              -{againstCount} {'反对'}
                            </span>
                          )}
                        </div>
                      )}

                      <AnimatePresence>
                        {isOpen && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            style={{ overflow: 'hidden' }}
                          >
                            <div style={{
                              marginTop: 8, paddingTop: 8,
                              borderTop: '1px solid var(--glass-border)',
                              fontSize: 9, color: 'var(--text-tertiary)',
                            }}>
                              {item.evidence_items.length > 0 && (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                                  {item.evidence_items.map((e, j) => (
                                    <span key={j} style={{
                                      padding: '2px 8px', borderRadius: 3,
                                      background: e.direction === 'support'
                                        ? 'rgba(16,185,129,0.05)' : 'rgba(248,113,113,0.04)',
                                      color: e.direction === 'support' ? 'var(--success)' : 'var(--danger)',
                                      fontFamily: 'var(--font-mono)', fontSize: 8,
                                      border: `1px solid ${e.direction === 'support'
                                        ? 'rgba(16,185,129,0.08)' : 'rgba(248,113,113,0.06)'}`,
                                    }}>
                                      {e.name} LR={e.lr}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {item.content_snippet && (
                                <div style={{
                                  padding: '6px 10px', fontSize: 8, lineHeight: 1.6, opacity: 0.5,
                                  borderLeft: '2px solid var(--glass-border)', marginBottom: 6,
                                }}>
                                  {item.content_snippet}
                                </div>
                              )}
                              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, opacity: 0.35 }}>
                                {'置信度追踪: '}
                                {item.bayesian_trace.map(t => t.toFixed(2)).join(' → ')}
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )
                })}
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Web results tab */}
      <AnimatePresence mode="wait">
        {activeTab === 'web' && (
          <motion.div
            key="web-tab"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              flex: 1, overflowY: 'auto', padding: '10px 14px',
              display: 'flex', flexDirection: 'column', gap: 8,
            }}
          >
            {result.web_results.length === 0 ? (
              <div style={{
                textAlign: 'center', padding: 30,
                fontSize: 10, color: 'var(--text-tertiary)', opacity: 0.5,
              }}>
                {'无网络搜索结果'}
              </div>
            ) : (
              result.web_results.map((wr, idx) => (
                <motion.a
                  key={idx}
                  variants={itemVariants}
                  initial="hidden"
                  animate="visible"
                  whileHover={{ scale: 1.01 }}
                  href={wr.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'block', padding: '10px 14px',
                    background: 'rgba(255,255,255,0.4)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--glass-border)',
                    textDecoration: 'none',
                  }}
                >
                  <div style={{
                    fontSize: 10, fontWeight: 600, color: 'var(--text-primary)',
                    display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4,
                  }}>
                    {wr.title || `结果 ${idx + 1}`}
                    <ArrowUpRight size={10} weight="bold" color="var(--text-tertiary)" />
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
                    {wr.snippet}
                  </div>
                  {wr.url && (
                    <div style={{
                      fontSize: 8, color: 'var(--text-tertiary)', opacity: 0.35, marginTop: 4,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {wr.url}
                    </div>
                  )}
                </motion.a>
              ))
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
