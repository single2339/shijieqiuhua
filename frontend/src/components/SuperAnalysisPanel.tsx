import { useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, PaperPlaneRight, X, Atom, Download, Globe, LinkSimple } from '@phosphor-icons/react'
import type { SuperAnalysisProgress } from '../api'
import type { SuperAnalysisResponse } from '../types'
import { useSuperAnalysis } from '../hooks/useSuperAnalysis'
import { parseAnalysis, highlightText, generateHTML } from '../lib/markdown'
import type { Block } from '../lib/markdown'

interface Props { onClose: () => void; isMobile?: boolean }

// ── Animation variants ──

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

const panelVariants = {
  hidden: { opacity: 0, scale: 0.96, y: 10 },
  visible: {
    opacity: 1, scale: 1, y: 0,
    transition: { type: 'spring' as const, stiffness: 100, damping: 20 },
  },
  exit: { opacity: 0, scale: 0.96, y: 10, transition: { duration: 0.18 } },
}

const contentVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1, y: 0,
    transition: { type: 'spring' as const, stiffness: 100, damping: 20, delay: 0.12 },
  },
}

const shimmerGradient = {
  animate: {
    x: ['-100%', '200%'],
    transition: { duration: 1.6, repeat: Infinity, ease: 'linear' as const },
  },
}

// ── Reasoning phases (real progress from backend) ──

const phaseMeta: Record<string, { label: string; icon: string }> = {
  collecting: { label: '情报整理', icon: '库' },
  crossmatching: { label: '关联匹配', icon: '证' },
  analyzing: { label: '推理结论', icon: '智' },
  // legacy phases kept for backward compatibility
  bayesian: { label: '情报整理', icon: '算' },
  searching: { label: '情报整理', icon: '网' },
  scanning: { label: '情报整理', icon: '库' },
  done: { label: '完成', icon: '✓' },
  error: { label: '出错', icon: '✗' },
}

const detailLabels: Record<string, string> = {
  total_docs: '文档总数',
  processed: '已处理',
  relevant_count: '相关情报',
  internal_count: '内部数据',
  web_count: '网络数据',
}

function ProgressDisplay({ progress, displayPercent }: { progress: SuperAnalysisProgress; displayPercent: number }) {
  const meta = phaseMeta[progress.phase] || { label: progress.message || '处理中...', icon: '··' }
  const elapsed = Math.floor(progress.elapsed_seconds)
  const min = Math.floor(elapsed / 60)
  const sec = elapsed % 60
  const elapsedStr = min > 0 ? `${min} 分 ${sec} 秒` : `${sec} 秒`

  // Sort phases in logical order for the progress bar
  const orderedPhases = ['collecting', 'crossmatching', 'analyzing']
  const currentIdx = orderedPhases.indexOf(progress.phase)
  const activePhase = currentIdx >= 0 ? progress.phase : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Current phase */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <motion.div
          animate={{ scale: [1, 1.05, 1], opacity: [0.8, 1, 0.8] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            width: 44, height: 44, borderRadius: 'var(--radius-md)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
            background: 'rgba(13,148,136,0.08)',
            color: 'var(--accent)',
            border: '2px solid rgba(13,148,136,0.15)',
          }}
        >
          {meta.icon}
        </motion.div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, flex: 1 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            {meta.label}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {progress.message || '处理中...'}
          </span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
            {displayPercent}%
          </span>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {elapsedStr}
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{
        width: '100%', height: 4, borderRadius: 2,
        background: 'var(--bg-elevated)',
        overflow: 'hidden',
      }}>
        <motion.div
          animate={{ width: `${Math.max(displayPercent, 2)}%` }}
          transition={{ duration: 0.6, ease: 'easeInOut' }}
          style={{
            height: '100%', borderRadius: 2,
            background: 'linear-gradient(90deg, var(--accent), #0d9488 60%, #06b6d4)',
            backgroundSize: '200% 100%',
          }}
        />
      </div>

      {/* Phase timeline */}
      <div style={{ display: 'flex', gap: 0, justifyContent: 'space-between' }}>
        {orderedPhases.map((phase, i) => {
          const phaseIdx = orderedPhases.indexOf(activePhase || '')
          const state: 'done' | 'active' | 'pending' =
            i < phaseIdx ? 'done' :
            i === phaseIdx ? 'active' :
            'pending'
          const meta = phaseMeta[phase]

          return (
            <div key={phase} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              flex: 1, maxWidth: 60,
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: state === 'done' ? 'var(--success)' :
                  state === 'active' ? 'var(--accent)' :
                  'var(--border-subtle)',
                transition: 'background 0.4s ease',
              }} />
              <span style={{
                fontSize: 8, textAlign: 'center',
                color: state === 'active' ? 'var(--accent)' :
                  state === 'done' ? 'var(--text-secondary)' :
                  'var(--text-tertiary)',
                fontFamily: 'var(--font-mono)',
                opacity: state === 'pending' ? 0.4 : 1,
                transition: 'opacity 0.4s ease, color 0.4s ease',
              }}>
                {meta?.label || phase}
              </span>
            </div>
          )
        })}
      </div>

      {progress.detail && Object.keys(progress.detail).length > 0 && (
        <div style={{
          display: 'flex', gap: 16, padding: '8px 12px',
          background: 'rgba(0,0,0,0.02)', borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--glass-border)',
        }}>
          {Object.entries(progress.detail).map(([key, val]) => {
            const label = detailLabels[key] || key
            return (
              <div key={key} style={{ display: 'flex', gap: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>{label}:</span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{String(val)}</span>
              </div>
            )
          })}
        </div>
      )}

      <motion.div
        animate={{ opacity: [0.25, 0.5, 0.25] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        style={{ color: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: 0.5, textAlign: 'center' }}
      >
        {'超级分析通常需要 1-5 分钟，复杂问题可能更久'}
      </motion.div>
    </div>
  )
}

export default function SuperAnalysisPanel({ onClose, isMobile }: Props) {
  const {
    question, setQuestion, loading, result, error, progress, displayPercent,
    handleSubmit, inputRef,
  } = useSuperAnalysis()
  const panelRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (result && contentRef.current) contentRef.current.scrollTop = 0
  }, [result])

  const handleDownload = useCallback(() => {
    if (!result) return
    const html = generateHTML(result)
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `super-analysis-${Date.now()}.html`
    a.click()
    URL.revokeObjectURL(url)
  }, [result])

  const analysisBlocks: Block[] = result ? parseAnalysis(result.analysis) : []

  return (
    <motion.div
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="hidden"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 'var(--z-overlay)',
        background: 'rgba(30,27,24,0.06)',
        backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 'max(20px, 4vw)',
      }}
    >
      <motion.div
        ref={panelRef}
        variants={panelVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        onClick={e => e.stopPropagation()}
        style={{
          width: isMobile ? '100%' : '92vw',
          maxWidth: isMobile ? '100%' : 1100,
          height: isMobile ? '100%' : '88vh',
          maxHeight: isMobile ? '100%' : 800,
          borderRadius: isMobile ? 0 : 'var(--radius-xl)',
          display: 'flex', flexDirection: 'column',
          background: 'var(--glass-bg)',
          border: isMobile ? 'none' : '1px solid var(--glass-border)',
          boxShadow: 'var(--shadow-diffuse), var(--glass-inner-shadow)',
          backdropFilter: 'blur(40px) saturate(180%)',
          WebkitBackdropFilter: 'blur(40px) saturate(180%)',
          overflow: 'hidden',
          fontFamily: 'var(--font-ui)',
        }}
      >
        {/* ── Header ── */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: '1px solid var(--glass-border)',
          flexShrink: 0,
          background: 'rgba(255,255,255,0.25)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Brain size={18} weight="duotone" color="var(--accent)" />
            <span style={{
              fontSize: 15, fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.01em',
              fontFamily: 'var(--font-display)',
            }}>
              {'超级分析'}
            </span>
            <motion.span
              animate={{
                boxShadow: [
                  '0 0 0 0 rgba(13,148,136,0)',
                  '0 0 0 4px rgba(13,148,136,0.06)',
                  '0 0 0 0 rgba(13,148,136,0)',
                ],
              }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
                padding: '2px 8px', borderRadius: 99,
                background: 'rgba(13,148,136,0.05)', border: '1px solid rgba(13,148,136,0.1)',
              }}
            >
              {'深度推理'}
            </motion.span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {result && (
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleDownload}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: 'rgba(16,185,129,0.05)',
                  border: '1px solid rgba(16,185,129,0.15)',
                  color: '#059669', cursor: 'pointer',
                  padding: '6px 14px', borderRadius: 'var(--radius-sm)',
                  fontSize: 12, fontWeight: 600,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <Download size={14} weight="duotone" />
                {'下载 HTML'}
              </motion.button>
            )}

            <motion.button
              whileHover={{ scale: 1.08, rotate: 90 }}
              whileTap={{ scale: 0.92 }}
              onClick={onClose}
              style={{
                background: 'rgba(0,0,0,0.03)', border: '1px solid var(--glass-border)',
                color: 'var(--text-tertiary)', cursor: 'pointer',
                width: 30, height: 30, borderRadius: 'var(--radius-sm)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <X size={14} weight="bold" />
            </motion.button>
          </div>
        </div>

        {/* ── Body: asymmetric split ── */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* ── LEFT: Main analysis area ── */}
          <div ref={contentRef} style={{
            flex: 1, overflowY: 'auto',
            padding: '20px 24px',
            display: 'flex', flexDirection: 'column', gap: 14,
          }}>
            {/* Welcome — asymmetric left-aligned */}
            {!result && !loading && !error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{ flex: 1, display: 'flex', alignItems: 'center', padding: '20px 0' }}
              >
                <div style={{ display: 'flex', gap: 28, alignItems: 'flex-start', maxWidth: 520 }}>
                  <div style={{
                    flexShrink: 0, width: 56, height: 56,
                    borderRadius: 'var(--radius-lg)',
                    background: 'rgba(13,148,136,0.04)',
                    border: '1px solid rgba(13,148,136,0.08)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Atom size={28} weight="duotone" color="var(--accent)" style={{ opacity: 0.5 }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{
                      fontSize: 16, fontWeight: 600,
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-display)',
                      letterSpacing: '-0.01em', lineHeight: 1.4,
                    }}>
                      {'输入任意问题，系统将结合情报数据进行深度推理分析'}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{
                        fontSize: 12, lineHeight: 1.7, color: 'var(--text-tertiary)',
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        <span style={{
                          width: 4, height: 4, borderRadius: '50%',
                          background: 'var(--accent)', opacity: 0.35, flexShrink: 0,
                        }} />
                        {'分析框架：假设陈述 → 先验评估 → 证据分析 → 后验更新 → 结论'}
                      </div>
                      <div style={{
                        fontSize: 12, lineHeight: 1.7, color: 'var(--text-tertiary)',
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        <span style={{
                          width: 4, height: 4, borderRadius: '50%',
                          background: 'var(--accent)', opacity: 0.35, flexShrink: 0,
                        }} />
                        {'自动搜索网络公开数据作为补充参考'}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Error */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  padding: '14px 18px',
                  color: 'var(--danger)', fontSize: 13,
                  background: 'rgba(220,38,38,0.03)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid rgba(220,38,38,0.08)',
                  display: 'flex', alignItems: 'center', gap: 10,
                }}
              >
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)', flexShrink: 0 }} />
                {error}
              </motion.div>
            )}

            {/* Loading — animated reasoning phases */}
            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14, padding: '12px 0' }}
              >
                {progress && <ProgressDisplay progress={progress} displayPercent={displayPercent} />}
              </motion.div>
            )}

            {/* Analysis result */}
            {result && (
              <motion.div
                variants={contentVariants}
                initial="hidden"
                animate="visible"
                style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
              >
                {/* Rendered analysis blocks */}
                <div style={{ fontSize: 14, lineHeight: 1.9, color: 'var(--text-primary)' }}>
                  {analysisBlocks.map((block, idx) => {
                    if (block.type === 'h2') {
                      return (
                        <div key={idx} style={{
                          fontSize: 17, fontWeight: 700, color: 'var(--accent)',
                          marginTop: idx > 0 ? 22 : 0, marginBottom: 10, paddingBottom: 8,
                          borderBottom: '1px solid var(--glass-border)',
                          fontFamily: 'var(--font-display)', letterSpacing: '-0.01em',
                        }}>
                          {block.text}
                        </div>
                      )
                    }
                    if (block.type === 'h3') {
                      return (
                        <div key={idx} style={{
                          fontSize: 14, fontWeight: 600, color: 'var(--text-primary)',
                          marginTop: 14, marginBottom: 8, paddingLeft: 10,
                          borderLeft: '2px solid var(--accent)',
                        }}>
                          {block.text}
                        </div>
                      )
                    }
                    if (block.type === 'list') {
                      return (
                        <div key={idx} style={{
                          fontSize: 13, lineHeight: 1.8, color: 'var(--text-secondary)',
                          marginBottom: 4, paddingLeft: 4, display: 'flex', gap: 8,
                        }}>
                          <span style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}>
                            {/^\d+\./.test(block.text) ? (block.text.match(/^\d+\./)![0]) : '—'}
                          </span>
                          <span>{highlightText(block.text.replace(/^[-*\d+\.]\s*/, ''))}</span>
                        </div>
                      )
                    }
                    if (block.type === 'code') {
                      return (
                        <div key={idx} style={{
                          margin: '8px 0', padding: '12px 16px',
                          background: 'rgba(30,27,24,0.03)', borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--glass-border)', fontFamily: 'var(--font-mono)',
                          fontSize: 12, lineHeight: 1.7, color: 'var(--text-secondary)',
                          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                        }}>
                          {block.text}
                        </div>
                      )
                    }
                    if (block.type === 'table') {
                      return (
                        <div key={idx} style={{
                          margin: '10px 0', overflowX: 'auto',
                          border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-sm)',
                        }}>
                          <table style={{
                            width: '100%', borderCollapse: 'collapse',
                            fontSize: 12, fontFamily: 'var(--font-mono)',
                          }}>
                            <thead>
                              <tr style={{ background: 'rgba(0,0,0,0.02)' }}>
                                {block.headers.map((h, hi) => (
                                  <th key={hi} style={{
                                    padding: '7px 12px', textAlign: 'left',
                                    fontWeight: 600, color: 'var(--text-primary)',
                                    fontSize: 11, borderBottom: '1px solid var(--glass-border)',
                                  }}>
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {block.rows.map((row, ri) => (
                                <tr key={ri}>
                                  {row.map((cell, ci) => (
                                    <td key={ci} style={{
                                      padding: '6px 12px', color: 'var(--text-secondary)',
                                      borderBottom: ri < block.rows.length - 1 ? '1px solid var(--glass-border)' : 'none',
                                      fontSize: 11,
                                    }}>
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )
                    }
                    return (
                      <div key={idx} style={{
                        fontSize: 13, lineHeight: 1.9, color: 'var(--text-secondary)',
                        marginBottom: 8,
                      }}>
                        {highlightText(block.text)}
                      </div>
                    )
                  })}
                </div>
              </motion.div>
            )}
          </div>

          {/* ── RIGHT: Sidebar — web results + relevant items (asymmetric split) ── */}
          {result && (result.web_results.length > 0 || result.relevant_items.length > 0) && (
            <div style={{
              width: 280, flexShrink: 0,
              borderLeft: '1px solid var(--glass-border)',
              overflowY: 'auto',
              background: 'rgba(0,0,0,0.01)',
              display: 'flex', flexDirection: 'column',
            }}>
              {/* Web results section */}
              {result.web_results.length > 0 && (
                <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--glass-border)' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    marginBottom: 10,
                    fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)', letterSpacing: 0.5,
                  }}>
                    <Globe size={12} weight="duotone" color="var(--text-tertiary)" />
                    网络参考
                    <span style={{
                      fontSize: 8, color: 'var(--text-tertiary)', opacity: 0.6,
                      marginLeft: 'auto',
                    }}>
                      {result.web_results.length} 条
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {result.web_results.slice(0, 8).map((wr, i) => (
                      <a
                        key={i}
                        href={wr.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'block', textDecoration: 'none',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--glass-border)',
                          background: 'var(--bg-surface)',
                          transition: 'border-color 0.15s ease',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--glass-border)' }}
                      >
                        <div style={{
                          display: 'flex', alignItems: 'flex-start', gap: 4,
                          fontSize: 10, lineHeight: 1.4, color: 'var(--text-primary)',
                          fontWeight: 500, marginBottom: 2,
                        }}>
                          <LinkSimple size={10} weight="bold" color="var(--text-tertiary)" style={{ flexShrink: 0, marginTop: 1 }} />
                          <span style={{
                            overflow: 'hidden', textOverflow: 'ellipsis',
                            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                          }}>
                            {wr.title || wr.url}
                          </span>
                        </div>
                        {wr.snippet && (
                          <div style={{
                            fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.4,
                            overflow: 'hidden', textOverflow: 'ellipsis',
                            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                            marginTop: 2,
                          }}>
                            {wr.snippet}
                          </div>
                        )}
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Relevant intel items section */}
              {result.relevant_items.length > 0 && (
                <div style={{ padding: '14px 16px', flex: 1 }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    marginBottom: 10,
                    fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)', letterSpacing: 0.5,
                  }}>
                    <Brain size={12} weight="duotone" color="var(--text-tertiary)" />
                    相关情报
                    <span style={{
                      fontSize: 8, color: 'var(--text-tertiary)', opacity: 0.6,
                      marginLeft: 'auto',
                    }}>
                      {result.relevant_items.length} 条
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {result.relevant_items.map((item, i) => (
                      <div key={i} style={{
                        padding: '6px 8px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--glass-border)',
                        background: 'var(--bg-surface)',
                      }}>
                        <div style={{
                          fontSize: 10, fontWeight: 500, color: 'var(--text-primary)',
                          lineHeight: 1.4, marginBottom: 3,
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                        }}>
                          {item.title}
                        </div>
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: 6,
                          fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
                        }}>
                          <span>{item.source}</span>
                          <span style={{ opacity: 0.4 }}>|</span>
                          <span>{item.date}</span>
                          <span style={{ opacity: 0.4 }}>|</span>
                          <span style={{
                            color: item.confidence >= 0.7 ? 'var(--success)' :
                              item.confidence >= 0.4 ? 'var(--warning)' : 'var(--danger)',
                            fontWeight: 600,
                          }}>
                            {Math.round(item.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Input bar ── */}
        <div style={{
          display: 'flex', gap: 10, padding: '12px 20px',
          borderTop: '1px solid var(--glass-border)',
          flexShrink: 0,
          background: 'rgba(255,255,255,0.25)',
        }}>
          <input
            ref={inputRef}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSubmit())}
            placeholder={'输入想要分析的问题（如：台海局势是否在恶化？）'}
            style={{
              flex: 1, background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)', padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: 13, fontFamily: 'var(--font-ui)',
              outline: 'none',
              transition: 'border-color 0.2s, box-shadow 0.2s',
            }}
            onFocus={e => {
              e.target.style.borderColor = 'var(--accent)'
              e.target.style.boxShadow = '0 0 0 3px rgba(13,148,136,0.06)'
            }}
            onBlur={e => {
              e.target.style.borderColor = 'var(--border-subtle)'
              e.target.style.boxShadow = 'none'
            }}
          />
          <motion.button
            whileHover={{ scale: loading || !question.trim() ? 1 : 1.02 }}
            whileTap={{ scale: loading || !question.trim() ? 1 : 0.96 }}
            onClick={handleSubmit}
            disabled={loading || !question.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: loading || !question.trim() ? 'var(--bg-elevated)' : 'var(--accent)',
              border: 'none',
              color: loading || !question.trim() ? 'var(--text-tertiary)' : '#ffffff',
              padding: '10px 22px', borderRadius: 'var(--radius-sm)',
              cursor: loading || !question.trim() ? 'default' : 'pointer',
              fontSize: 13, fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              opacity: loading || !question.trim() ? 0.3 : 1,
              transition: 'opacity 0.15s',
            }}
          >
            {loading ? '推理中...' : (
              <>
                {'分析'}
                <PaperPlaneRight size={13} weight="fill" />
              </>
            )}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  )
}
