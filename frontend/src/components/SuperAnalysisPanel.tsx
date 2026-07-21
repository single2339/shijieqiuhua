import { useRef, useEffect, useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { Brain, PaperPlaneRight, X, Atom, Download, Globe, LinkSimple } from '@phosphor-icons/react'
import type { SuperAnalysisProgress } from '../api'
import type { SuperAnalysisResponse } from '../types'
import { useSuperAnalysis } from '../hooks/useSuperAnalysis'
import { useFloatingPanel } from '../hooks/useFloatingPanel'
import { parseAnalysis, highlightText, generateHTML } from '../lib/markdown'
import type { Block } from '../lib/markdown'
import { safeExternalUrl } from '../utils/safeUrl'
import { confidenceColor } from '../utils/intelDisplay'

interface Props {
  onClose: () => void
  isMobile?: boolean
  startDate?: string
  endDate?: string
}

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

const playbookOptions = [
  ['general', '通用分析'],
  ['person', '人员调查'],
  ['website', '网站/机构'],
  ['image', '图片取证'],
  ['identity', '身份关联'],
  ['event', '事件归因'],
  ['threat', '威胁/IOC'],
] as const

const controlStyle = {
  background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
  color: 'var(--text-secondary)', borderRadius: 'var(--radius-sm)',
  fontSize: 11, fontFamily: 'var(--font-ui)', padding: '7px 9px', outline: 'none',
}

const reviewButtonStyle = {
  background: 'var(--accent-dim)', border: '1px solid var(--glass-border)',
  color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)',
  fontSize: 10, fontFamily: 'var(--font-ui)', padding: '7px 9px', cursor: 'pointer',
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
            background: 'var(--accent-dim)',
            color: 'var(--accent)',
            border: '2px solid rgba(200,164,93,0.20)',
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

export default function SuperAnalysisPanel({ onClose, isMobile, startDate = '', endDate = '' }: Props) {
  const {
    question, setQuestion, loading, result, error, progress, displayPercent,
    investigationType, setInvestigationType, target, setTarget, purpose, setPurpose,
    authorized, setAuthorized, verificationDepth, setVerificationDepth, handleSubmit, submitReview, reviewing, inputRef,
  } = useSuperAnalysis({ startDate, endDate })
  const [reviewNotes, setReviewNotes] = useState('')
  const panelRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const floating = useFloatingPanel({
    enabled: !isMobile,
    width: 860,
    height: 620,
    anchor: 'right',
  })

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
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }, [result])

  const analysisBlocks: Block[] = result ? parseAnalysis(result.analysis) : []
  const needsTarget = investigationType !== 'general'
  const needsAuthorization = investigationType === 'person' || investigationType === 'identity'
  const submitDisabled = loading || !question.trim() || (needsTarget && !target.trim()) || (needsAuthorization && (!purpose.trim() || !authorized))

  return (
    <motion.div
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="hidden"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 'var(--z-overlay)',
        background: isMobile ? 'rgba(30,27,24,0.06)' : 'transparent',
        backdropFilter: isMobile ? 'blur(2px)' : 'none',
        display: 'flex', alignItems: 'center', justifyContent: isMobile ? 'center' : 'flex-start',
        pointerEvents: isMobile ? 'auto' : 'none',
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
          position: isMobile ? 'relative' : 'fixed',
          width: isMobile ? '100%' : 860,
          maxWidth: isMobile ? '100%' : '94vw',
          height: isMobile ? '100%' : 'min(620px, 78vh)',
          maxHeight: isMobile ? '100%' : '78vh',
          borderRadius: isMobile ? 0 : 'var(--radius-lg)',
          display: 'flex', flexDirection: 'column',
          background: 'var(--glass-bg)',
          border: isMobile ? 'none' : '1px solid var(--glass-border)',
          boxShadow: 'var(--shadow-diffuse), var(--glass-inner-shadow)',
          backdropFilter: 'blur(40px) saturate(180%)',
          WebkitBackdropFilter: 'blur(40px) saturate(180%)',
          overflow: 'hidden',
          fontFamily: 'var(--font-ui)',
          pointerEvents: 'auto',
          ...floating.panelStyle,
        }}
      >
        {/* ── Header ── */}
        <div {...floating.dragHandleProps} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid var(--glass-border)',
          flexShrink: 0,
          background: 'rgba(18,20,22,0.72)',
          ...floating.dragHandleStyle,
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
                  '0 0 0 0 rgba(200,164,93,0)',
                  '0 0 0 4px rgba(200,164,93,0.08)',
                  '0 0 0 0 rgba(200,164,93,0)',
                ],
              }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
                padding: '2px 8px', borderRadius: 99,
                background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.18)',
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
                  background: 'rgba(79,188,141,0.08)',
                  border: '1px solid rgba(79,188,141,0.18)',
                  color: 'var(--success)', cursor: 'pointer',
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
            padding: '14px 16px',
            display: 'flex', flexDirection: 'column', gap: 14,
            minWidth: 0,
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
                    background: 'rgba(32,36,40,0.72)',
                    border: '1px solid var(--glass-border)',
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
                  background: 'rgba(217,107,98,0.08)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid rgba(217,107,98,0.16)',
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
                {result.collection_status === 'empty' && (
                  <div style={{
                    padding: '10px 12px',
                    border: '1px solid var(--glass-border)',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(0,0,0,0.02)',
                    color: 'var(--text-secondary)',
                    fontSize: 11,
                    lineHeight: 1.7,
                  }}>
                    <div style={{ fontWeight: 700 }}>未找到相关情报</div>
                    <div>数据源均已正常查询，但没有与问题匹配的结果。</div>
                  </div>
                )}

                {result.collection_status !== 'empty' && (result.degraded || result.collection_status !== 'complete' || result.analysis_status !== 'complete' || result.errors.length > 0) && (
                  <div style={{
                    padding: '10px 12px',
                    border: '1px solid rgba(224,169,74,0.3)',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(224,169,74,0.08)',
                    color: 'var(--warning)',
                    fontSize: 11,
                    lineHeight: 1.7,
                  }}>
                    <div style={{ fontWeight: 700, marginBottom: 2 }}>降级分析</div>
                    <div>采集状态：{result.collection_status}</div>
                    <div>分析状态：{result.analysis_status}</div>
                    <div>
                      数据源：
                      {Object.entries(result.provider_statuses)
                        .map(([provider, status]) => `${provider}=${status}`)
                        .join('，') || '无'}
                    </div>
                    {result.errors.map((message, index) => (
                      <div key={`${index}-${message}`}>{message}</div>
                    ))}
                  </div>
                )}

                {result.hypothesis_assessment && (
                  <div style={{
                    padding: '14px 16px',
                    border: '1px solid var(--glass-border)',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(13,148,136,0.04)',
                  }}>
                    <div style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: 'var(--accent)',
                      marginBottom: 8,
                    }}>
                      结构化假设评估
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 8 }}>
                      {result.hypothesis_assessment.hypothesis}
                    </div>
                    <div style={{
                      display: 'flex',
                      gap: 10,
                      flexWrap: 'wrap',
                      fontSize: 10,
                      color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-mono)',
                    }}>
                      <span style={{
                        color: confidenceColor(result.hypothesis_assessment.confidence_level),
                        fontWeight: 700,
                      }}>
                        {result.hypothesis_assessment.confidence_level}
                      </span>
                      <span>先验 {Math.round(result.hypothesis_assessment.prior_probability * 100)}%</span>
                      <span>后验 {Math.round(result.hypothesis_assessment.posterior_probability * 100)}%</span>
                      <span>判定 {result.hypothesis_assessment.verdict}</span>
                      <span>独立证据源 {result.hypothesis_assessment.independent_source_count}</span>
                    </div>
                    {result.hypothesis_assessment.evidence.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                        {result.hypothesis_assessment.evidence.map(evidence => (
                          <div
                            key={evidence.evidence_id}
                            style={{
                              paddingTop: 7,
                              borderTop: '1px solid var(--glass-border)',
                              fontSize: 10,
                              lineHeight: 1.6,
                              color: 'var(--text-secondary)',
                            }}
                          >
                            <div style={{ fontFamily: 'var(--font-mono)' }}>
                              {evidence.evidence_id} · {evidence.relation}/{evidence.strength}
                              {' · '}LR {evidence.likelihood_ratio}
                              {' · '}后验 {Math.round(evidence.posterior_probability * 100)}%
                            </div>
                            <div>{evidence.rationale}</div>
                            <div style={{ color: 'var(--text-tertiary)' }}>{evidence.source}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {result.investigation && (
                  <div style={{
                    padding: '14px 16px', border: '1px solid var(--glass-border)',
                    borderRadius: 'var(--radius-sm)', background: 'rgba(13,148,136,0.025)',
                    display: 'flex', flexDirection: 'column', gap: 12,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 700 }}>调查证据与复核</div>
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                        {result.investigation.plan.playbook} · 分析师复核：{result.investigation.analyst_review.status}
                      </span>
                    </div>

                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>证据账本</div>
                      {result.investigation.evidence.map(item => (
                        <div key={item.id} style={{ borderTop: '1px solid var(--glass-border)', padding: '6px 0', fontSize: 10, lineHeight: 1.6 }}>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{item.id}</span>
                          <span style={{ color: 'var(--text-primary)', marginLeft: 6 }}>{item.title}</span>
                          <span style={{ color: 'var(--text-tertiary)', marginLeft: 6 }}>{item.verification_status} · {item.provenance}</span>
                          {item.summary && <div style={{ color: 'var(--text-secondary)' }}>{item.summary}</div>}
                        </div>
                      ))}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>关系网络</div>
                        {result.investigation.relationship_graph.edges.length > 0 ? result.investigation.relationship_graph.edges.map((edge, index) => (
                          <div key={`${edge.source}-${edge.target}-${index}`} style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>
                            {edge.source} — {edge.relation} → {edge.target}
                          </div>
                        )) : <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>暂无可复核关系</div>}
                      </div>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>时间线</div>
                        {result.investigation.timeline.map(item => (
                          <div key={item.date} style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>{item.date} · {item.summary}</div>
                        ))}
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>替代解释</div>
                        {result.investigation.alternative_explanations.map(item => (
                          <div key={item.id} style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>• {item.explanation}</div>
                        ))}
                      </div>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>待核验项</div>
                        {result.investigation.pending_verification.map(item => (
                          <div key={item.id} style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>• {item.question}</div>
                        ))}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      <input
                        value={reviewNotes}
                        onChange={event => setReviewNotes(event.target.value)}
                        placeholder="复核备注（可选）"
                        style={{ ...controlStyle, flex: 1, minWidth: 180 }}
                      />
                      <button type="button" disabled={reviewing} onClick={() => submitReview('approved', reviewNotes)} style={reviewButtonStyle}>
                        批准结论
                      </button>
                      <button type="button" disabled={reviewing} onClick={() => submitReview('needs_follow_up', reviewNotes)} style={reviewButtonStyle}>
                        需要补证
                      </button>
                      <button type="button" disabled={reviewing} onClick={() => submitReview('rejected', reviewNotes)} style={reviewButtonStyle}>
                        驳回结论
                      </button>
                    </div>
                  </div>
                )}

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
              width: 240, flexShrink: 0,
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
                    网络摘要（未验证）
                    <span style={{
                      fontSize: 8, color: 'var(--text-tertiary)', opacity: 0.6,
                      marginLeft: 'auto',
                    }}>
                      {result.web_results.length} 条
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {result.web_results.slice(0, 8).map((wr, i) => {
                      const resultUrl = safeExternalUrl(wr.url)
                      if (!resultUrl) return null
                      return (
                      <a
                        key={i}
                        href={resultUrl}
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
                      )
                    })}
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
                        </div>
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
                          marginTop: 4, fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
                        }}>
                          <span>聚合独立来源 {item.independent_source_count}</span>
                          <span>文档质量 {Math.round(item.quality_score * 100)}%</span>
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
          display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 14px',
          borderTop: '1px solid var(--glass-border)',
          flexShrink: 0,
          background: 'rgba(18,20,22,0.72)',
        }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <label style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              调查剧本
              <select value={investigationType} onChange={e => setInvestigationType(e.target.value as typeof investigationType)} style={{ ...controlStyle, marginLeft: 5 }}>
                {playbookOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            {needsTarget && (
              <input value={target} onChange={e => setTarget(e.target.value)} placeholder="调查目标（域名、人物、图片 URL、事件或 IOC）" style={{ ...controlStyle, flex: 1, minWidth: 180 }} />
            )}
            <label style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              验证深度
              <select value={verificationDepth} onChange={e => setVerificationDepth(e.target.value as typeof verificationDepth)} style={{ ...controlStyle, marginLeft: 5 }}>
                <option value="standard">标准</option>
                <option value="deep">深度</option>
              </select>
            </label>
          </div>
          {needsAuthorization && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input value={purpose} onChange={e => setPurpose(e.target.value)} placeholder="合法调查目的" style={{ ...controlStyle, flex: 1, minWidth: 180 }} />
              <label style={{ fontSize: 10, color: 'var(--text-secondary)', display: 'flex', gap: 5, alignItems: 'center' }}>
                <input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} />
                授权确认：我已获授权且仅处理必要的公开信息
              </label>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
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
              e.target.style.boxShadow = '0 0 0 3px rgba(200,164,93,0.10)'
            }}
            onBlur={e => {
              e.target.style.borderColor = 'var(--border-subtle)'
              e.target.style.boxShadow = 'none'
            }}
          />
          <motion.button
            whileHover={{ scale: submitDisabled ? 1 : 1.02 }}
            whileTap={{ scale: loading || !question.trim() ? 1 : 0.96 }}
            onClick={handleSubmit}
            disabled={submitDisabled}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: submitDisabled ? 'var(--bg-elevated)' : 'var(--accent)',
              border: 'none',
              color: submitDisabled ? 'var(--text-tertiary)' : 'var(--bg-deep)',
              padding: '10px 16px', borderRadius: 'var(--radius-sm)',
              cursor: submitDisabled ? 'default' : 'pointer',
              fontSize: 13, fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              opacity: submitDisabled ? 0.3 : 1,
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
        </div>
      </motion.div>
    </motion.div>
  )
}
