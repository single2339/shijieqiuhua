import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, PaperPlaneRight, FadersHorizontal, X, Atom, Download, Globe, ArrowUpRight } from '@phosphor-icons/react'
import { superAnalyze } from '../api'
import type { SuperAnalysisResponse } from '../types'
import { parseAnalysis, highlightText, generateMarkdown } from '../lib/markdown'
import type { Block } from '../lib/markdown'
import SuperAnalysisSidebar from './SuperAnalysisSidebar'

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
    transition: { type: 'spring' as const, stiffness: 90, damping: 20, mass: 0.8 },
  },
  exit: { opacity: 0, scale: 0.96, y: 10, transition: { duration: 0.18 } },
}

const contentVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1, y: 0,
    transition: { type: 'spring' as const, stiffness: 80, damping: 18, delay: 0.12 },
  },
}

const shimmerGradient = {
  animate: {
    x: ['-100%', '200%'],
    transition: { duration: 1.6, repeat: Infinity, ease: 'linear' as const },
  },
}

// ── Component ──

export default function SuperAnalysisPanel({ onClose, isMobile }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SuperAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [expandedItem, setExpandedItem] = useState<number | null>(null)
  const [showWebResults, setShowWebResults] = useState(false)
  const [activeTab, setActiveTab] = useState<'intel' | 'web'>('intel')
  const inputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (!loading) inputRef.current?.focus() }, [loading])
  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => {
    if (result && contentRef.current) contentRef.current.scrollTop = 0
  }, [result])

  const handleSubmit = async () => {
    const q = question.trim()
    if (!q || loading) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const timeoutId = setTimeout(() => controller.abort(), 120_000)
      const res = await superAnalyze(
        { question: q, start_date: startDate, end_date: endDate },
        controller.signal,
      )
      clearTimeout(timeoutId)
      setResult(res)
      abortRef.current = null
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (controller.signal.aborted && abortRef.current === controller) {
          setError('分析请求超时（120秒），请简化问题后重试')
        }
      } else if (err instanceof TypeError) {
        setError('网络连接失败，请检查网络后重试')
      } else if (err instanceof Error) {
        setError(err.message.startsWith('API error')
          ? `服务端错误：${err.message}`
          : `请求失败：${err.message}`)
      } else {
        setError('分析请求失败，请重试')
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setLoading(false)
    }
  }

  const handleDownload = useCallback(() => {
    if (!result) return
    const md = generateMarkdown(result)
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `super-analysis-${Date.now()}.md`
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
        position: 'fixed', inset: 0, zIndex: 2000,
        background: 'rgba(30,27,24,0.06)',
        backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
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
              fontSize: 13, fontWeight: 700,
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
                  fontSize: 10, fontWeight: 600,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <Download size={12} weight="duotone" />
                {'下载 Markdown'}
              </motion.button>
            )}

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setShowFilters(!showFilters)}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: showFilters ? 'rgba(13,148,136,0.05)' : 'rgba(0,0,0,0.02)',
                border: showFilters ? '1px solid rgba(13,148,136,0.12)' : '1px solid var(--glass-border)',
                color: showFilters ? 'var(--accent)' : 'var(--text-tertiary)',
                cursor: 'pointer',
                padding: '6px 12px', borderRadius: 'var(--radius-sm)',
                fontSize: 10, fontFamily: 'var(--font-mono)',
              }}
            >
              <FadersHorizontal size={12} weight="duotone" />
              {'日期筛选'}
            </motion.button>

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

        {/* ── Date filters (collapsible) ── */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: 'hidden', flexShrink: 0 }}
            >
              <div style={{
                display: 'flex', gap: 10, padding: '8px 20px',
                borderBottom: '1px solid var(--glass-border)',
                background: 'rgba(0,0,0,0.01)',
              }}>
                <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                  style={{
                    background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)', padding: '5px 10px',
                    borderRadius: 'var(--radius-sm)', fontSize: 10,
                    fontFamily: 'var(--font-mono)', width: 130,
                  }} />
                <span style={{ color: 'var(--text-tertiary)', fontSize: 10, display: 'flex', alignItems: 'center' }}>
                  {'至'}
                </span>
                <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                  style={{
                    background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)', padding: '5px 10px',
                    borderRadius: 'var(--radius-sm)', fontSize: 10,
                    fontFamily: 'var(--font-mono)', width: 130,
                  }} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

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
                      fontSize: 14, fontWeight: 600,
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-display)',
                      letterSpacing: '-0.01em', lineHeight: 1.4,
                    }}>
                      {'输入任意问题，系统将结合情报数据进行深度推理分析'}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{
                        fontSize: 10, lineHeight: 1.7, color: 'var(--text-tertiary)',
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        <span style={{
                          width: 4, height: 4, borderRadius: '50%',
                          background: 'var(--accent)', opacity: 0.35, flexShrink: 0,
                        }} />
                        {'分析框架：假设陈述 → 先验评估 → 证据分析 → 后验更新 → 结论'}
                      </div>
                      <div style={{
                        fontSize: 10, lineHeight: 1.7, color: 'var(--text-tertiary)',
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
                  color: 'var(--danger)', fontSize: 11,
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

            {/* Loading — skeleton shimmer */}
            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, padding: '8px 0' }}
              >
                <div style={{
                  position: 'relative', height: 28, width: '45%',
                  borderRadius: 'var(--radius-sm)', background: 'rgba(0,0,0,0.04)', overflow: 'hidden',
                }}>
                  <motion.div
                    variants={shimmerGradient}
                    animate="animate"
                    style={{
                      position: 'absolute', inset: 0, width: '60%',
                      background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.5) 50%, transparent 100%)',
                    }}
                  />
                </div>
                {[85, 92, 70, 88, 55].map((w, i) => (
                  <div key={i} style={{
                    position: 'relative', height: 12, width: `${w}%`,
                    borderRadius: 4, background: 'rgba(0,0,0,0.03)', overflow: 'hidden',
                  }}>
                    <motion.div
                      variants={shimmerGradient}
                      animate="animate"
                      style={{
                        position: 'absolute', inset: 0, width: '60%',
                        background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                      }}
                    />
                  </div>
                ))}
                <div style={{
                  position: 'relative', height: 80, width: '100%',
                  borderRadius: 'var(--radius-sm)', background: 'rgba(0,0,0,0.025)', overflow: 'hidden', marginTop: 8,
                }}>
                  <motion.div
                    variants={shimmerGradient}
                    animate="animate"
                    style={{
                      position: 'absolute', inset: 0, width: '40%',
                      background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
                  <motion.div
                    animate={{ opacity: [0.3, 0.7, 0.3] }}
                    transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                    style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent)' }}
                  />
                  <span style={{ color: 'var(--text-tertiary)', fontSize: 10, fontFamily: 'var(--font-mono)' }}>
                    {'深度推理中 — 搜索网络数据 · 评估证据 · 计算后验'}
                  </span>
                </div>
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
                {/* Web results badge */}
                {result.web_results.length > 0 && (
                  <motion.button
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setShowWebResults(!showWebResults)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px',
                      background: showWebResults ? 'rgba(13,148,136,0.04)' : 'rgba(13,148,136,0.015)',
                      border: showWebResults ? '1px solid rgba(13,148,136,0.12)' : '1px solid rgba(13,148,136,0.06)',
                      borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                      fontSize: 10, color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-mono)', textAlign: 'left',
                    }}
                  >
                    <Globe size={14} weight="duotone" color="var(--accent)" />
                    <span>
                      {'网络搜索到 '}
                      <strong style={{ color: 'var(--accent)' }}>{result.web_results.length}</strong>
                      {' 条相关数据'}
                    </span>
                    <span style={{ fontSize: 9, opacity: 0.35, marginLeft: 'auto' }}>
                      {showWebResults ? '收起' : '展开'}
                    </span>
                  </motion.button>
                )}

                {/* Web results expanded */}
                <AnimatePresence>
                  {showWebResults && result.web_results.length > 0 && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      style={{
                        overflow: 'hidden', borderRadius: 'var(--radius-sm)',
                        border: '1px solid rgba(13,148,136,0.06)',
                      }}
                    >
                      <div style={{
                        display: 'flex', flexDirection: 'column', gap: 6,
                        padding: '10px 14px', maxHeight: 180, overflowY: 'auto',
                      }}>
                        {result.web_results.map((wr, idx) => (
                          <div key={idx} style={{
                            fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.6,
                            padding: '6px 0',
                            borderBottom: idx < result.web_results.length - 1 ? '1px solid var(--glass-border)' : 'none',
                          }}>
                            <a href={wr.url} target="_blank" rel="noopener noreferrer"
                              style={{
                                color: 'var(--text-secondary)', fontWeight: 600,
                                textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4,
                              }}>
                              {wr.title || `结果 ${idx + 1}`}
                              <ArrowUpRight size={9} weight="bold" />
                            </a>
                            <div style={{ marginTop: 2, opacity: 0.6 }}>{wr.snippet}</div>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Rendered analysis blocks */}
                <div style={{ fontSize: 12, lineHeight: 1.9, color: 'var(--text-primary)' }}>
                  {analysisBlocks.map((block, idx) => {
                    if (block.type === 'h2') {
                      return (
                        <div key={idx} style={{
                          fontSize: 14, fontWeight: 700, color: 'var(--accent)',
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
                          fontSize: 11, fontWeight: 600, color: 'var(--text-primary)',
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
                          fontSize: 11, lineHeight: 1.8, color: 'var(--text-secondary)',
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
                          fontSize: 9, lineHeight: 1.7, color: 'var(--text-secondary)',
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
                            fontSize: 10, fontFamily: 'var(--font-mono)',
                          }}>
                            <thead>
                              <tr style={{ background: 'rgba(0,0,0,0.02)' }}>
                                {block.headers.map((h, hi) => (
                                  <th key={hi} style={{
                                    padding: '7px 12px', textAlign: 'left',
                                    fontWeight: 600, color: 'var(--text-primary)',
                                    fontSize: 9, borderBottom: '1px solid var(--glass-border)',
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
                                      fontSize: 9,
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
                        fontSize: 11, lineHeight: 1.9, color: 'var(--text-secondary)',
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

          {/* ── RIGHT: Sidebar ── */}
          {result && (
            <SuperAnalysisSidebar
              result={result}
              expandedItem={expandedItem}
              setExpandedItem={setExpandedItem}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
            />
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
              fontSize: 11, fontFamily: 'var(--font-ui)',
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
              fontSize: 11, fontWeight: 600,
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
