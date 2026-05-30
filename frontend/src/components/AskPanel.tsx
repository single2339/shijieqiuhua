import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { PaperPlaneRight, ChatCircleDots, FadersHorizontal, X } from '@phosphor-icons/react'
import { askQuestion } from '../api'
import type { AskResponse, IntelLayer } from '../types'
import { LAYER_META } from '../types'

interface Props { onClose: () => void; isMobile?: boolean }

const ALL_LAYERS: IntelLayer[] = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber']

interface Message { role: 'user' | 'assistant'; content: string; refs?: AskResponse['references'] }

function TypewriterText({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (text.length < 20) { setDisplayed(text); setDone(true); return }
    setDisplayed('')
    setDone(false)
    let i = 0
    const id = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) { clearInterval(id); setDone(true) }
    }, 15)
    return () => clearInterval(id)
  }, [text])

  return (
    <span>
      {displayed}
      {!done && <span style={{ opacity: 0.6, animation: 'pulse-glow 1s ease-in-out infinite' }}>▊</span>}
    </span>
  )
}

export default function AskPanel({ onClose, isMobile }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: '你好，我是 AI 情报分析师。你可以向我提问关于当前情报数据的任何问题。' },
  ])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [layer, setLayer] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => { if (!loading) inputRef.current?.focus() }, [loading])

  const handleSubmit = async () => {
    const q = question.trim()
    if (!q || loading) return
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setQuestion('')
    setLoading(true)
    try {
      const res = await askQuestion({ question: q, start_date: startDate, end_date: endDate, layer })
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer, refs: res.references }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '请求失败，请稍后重试。' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ y: 20, opacity: 0, scale: 0.97 }}
      animate={{ y: 0, opacity: 1, scale: 1 }}
      exit={{ y: 20, opacity: 0, scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      className={isMobile ? 'glass-panel mobile-full-panel' : 'glass-panel'}
      style={{
        position: 'fixed',
        bottom: isMobile ? 0 : 16,
        left: isMobile ? 0 : '50%',
        transform: isMobile ? 'none' : 'translateX(-50%)',
        width: isMobile ? '100%' : 560,
        maxWidth: isMobile ? '100%' : '94vw',
        height: isMobile ? '100%' : 480,
        maxHeight: isMobile ? '100%' : undefined,
        borderRadius: isMobile ? 0 : 'var(--radius-lg)',
        zIndex: 1000,
        boxShadow: 'var(--shadow-diffuse)',
        display: 'flex', flexDirection: 'column',
        fontFamily: 'var(--font-ui)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 18px', borderBottom: '1px solid var(--glass-border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ChatCircleDots size={16} weight="duotone" color="var(--accent)" />
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 1, fontFamily: 'var(--font-display)' }}>
            AI 情报分析师
          </span>
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={() => setShowFilters(!showFilters)}
            style={{
              background: 'rgba(0,0,0,0.04)', border: '1px solid var(--glass-border)',
              color: showFilters ? 'var(--accent)' : 'var(--text-tertiary)', cursor: 'pointer',
              padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: 9,
              fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            <FadersHorizontal size={10} weight="duotone" />
            {showFilters ? '收起筛选' : '筛选'}
          </motion.button>
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
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}
        >
          <X size={12} weight="bold" />
        </motion.button>
      </div>

      {/* Filters */}
      {showFilters && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          style={{
            display: 'flex', gap: 8, padding: '8px 18px',
            borderBottom: '1px solid var(--glass-border)', flexWrap: 'wrap',
            background: 'var(--bg-deep)', fontSize: 10, overflow: 'hidden',
          }}
        >
          <select value={layer} onChange={e => setLayer(e.target.value)}
            className="panel-select"
            style={{
              background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)', padding: '3px 8px', borderRadius: 'var(--radius-sm)',
              fontSize: 10, fontFamily: 'var(--font-mono)',
            }}>
            <option value="">全部图层</option>
            {ALL_LAYERS.map(l => (
              <option key={l} value={l}>{LAYER_META[l].label}</option>
            ))}
          </select>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="panel-select"
            style={{
              background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)', padding: '3px 8px', borderRadius: 'var(--radius-sm)',
              fontSize: 10, fontFamily: 'var(--font-mono)', width: 120,
            }} />
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="panel-select"
            style={{
              background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)', padding: '3px 8px', borderRadius: 'var(--radius-sm)',
              fontSize: 10, fontFamily: 'var(--font-mono)', width: 120,
            }} />
        </motion.div>
      )}

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '12px 18px',
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
            }}
          >
            <div style={{
              background: m.role === 'user' ? 'rgba(16,185,129,0.06)' : 'var(--bg-deep)',
              border: `1px solid ${m.role === 'user' ? 'rgba(16,185,129,0.2)' : 'var(--border-subtle)'}`,
              borderLeft: m.role === 'user' ? '2px solid var(--accent)' : 'none',
              borderRadius: 'var(--radius-md)', padding: '8px 12px',
              fontSize: 12, lineHeight: 1.6, color: 'var(--text-primary)',
              whiteSpace: 'pre-wrap',
            }}>
              {m.role === 'assistant' && i === messages.length - 1 && loading
                ? <TypewriterText text={m.content} />
                : m.content}
            </div>
            {m.refs && m.refs.length > 0 && (
              <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {m.refs.slice(0, 5).map((ref, j) => (
                  <span key={j} style={{
                    fontSize: 8, color: 'var(--text-tertiary)',
                    background: 'var(--bg-surface)', padding: '1px 6px',
                    borderRadius: 3, border: '1px solid var(--border-subtle)',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {ref.source} · {ref.date}
                  </span>
                ))}
              </div>
            )}
          </motion.div>
        ))}

        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ alignSelf: 'flex-start' }}
          >
            <motion.span
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              style={{ color: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                style={{ width: 10, height: 10, borderRadius: '50%', border: '2px solid var(--border-subtle)', borderTopColor: 'var(--accent)', display: 'inline-block' }}
              />
              分析中…
            </motion.span>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        display: 'flex', gap: 8, padding: '10px 18px',
        borderTop: '1px solid var(--glass-border)',
      }}>
        <input
          ref={inputRef}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSubmit())}
          placeholder="输入情报分析问题..."
          className="panel-input"
          style={{
            flex: 1, background: 'var(--bg-deep)', border: '1px solid var(--border-subtle)',
            color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 'var(--radius-sm)',
            fontSize: 11, fontFamily: 'var(--font-ui)', outline: 'none',
          }}
        />
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleSubmit}
          disabled={loading || !question.trim()}
          style={{
            background: loading || !question.trim() ? 'var(--bg-elevated)' : 'var(--accent)',
            border: 'none', color: loading || !question.trim() ? 'var(--text-tertiary)' : '#fff',
            padding: '7px 16px', borderRadius: 'var(--radius-sm)',
            cursor: loading || !question.trim() ? 'default' : 'pointer',
            fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)',
            display: 'flex', alignItems: 'center', gap: 6,
            opacity: loading || !question.trim() ? 0.4 : 1,
            transition: 'opacity 0.15s ease',
          }}
        >
          {loading ? '分析中...' : (
            <>
              发送 <PaperPlaneRight size={12} weight="fill" />
            </>
          )}
        </motion.button>
      </div>
    </motion.div>
  )
}
