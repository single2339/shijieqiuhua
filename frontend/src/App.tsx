import { useMemo, useState } from 'react'
import { ArrowRight, Clock, Question } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { askFootballQuestion } from './shijieqiuhua/api'
import { MATCHES } from './shijieqiuhua/mockData'
import type { FootballMatch, FootballQuestionAnswer } from './shijieqiuhua/types'
import AuthGate from './shijieqiuhua/components/AuthGate'
import type { UserTier } from './shijieqiuhua/components/AuthGate'
import AccountStatus from './shijieqiuhua/components/AccountStatus'
import './shijieqiuhua.css'

export default function App() {
  const [selectedId, setSelectedId] = useState(MATCHES[0].id)
  const [question, setQuestion] = useState('上半场角球会不会偏多？')
  const [answer, setAnswer] = useState<FootballQuestionAnswer | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [userTier] = useState<UserTier>('paid') // W3.5 wire real auth

  const selectedMatch = useMemo(
    () => MATCHES.find(m => m.id === selectedId) ?? MATCHES[0],
    [selectedId],
  )

  async function ask(next = question) {
    setQuestion(next)
    setLoading(true)
    setError('')
    setAnswer(null)
    try {
      setAnswer(await askFootballQuestion({
        home_team: selectedMatch.homeTeam,
        away_team: selectedMatch.awayTeam,
        kickoff_at: selectedMatch.kickoffAt,
        competition: selectedMatch.league,
        question: next,
      }))
    } catch (e) {
      setError(e instanceof Error ? e.message : '问题处理失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="sqh-app">
      <header className="sqh-topbar">
        <div className="sqh-brand">
          <div className="sqh-mark">世</div>
          <div><h1>世界球花</h1><p>足球情报问答</p></div>
        </div>
      </header>

      <section className="sqh-shell">
        {/* left */}
        <aside className="sqh-panel sqh-match-rail" aria-label="赛事列表">
          <div className="sqh-section-title"><Clock size={16} weight="duotone" /><span>今日赛事</span></div>
          <div className="sqh-match-list">
            {MATCHES.map(m => (
              <button key={m.id} className="sqh-match-row" data-active={m.id === selectedId}
                onClick={() => { setSelectedId(m.id); setAnswer(null); setError('') }}>
                <span className="sqh-match-league">{m.league}</span>
                <strong>{m.homeTeam} vs {m.awayTeam}</strong>
                <span>{m.kickoffAt} · {m.publicLean}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* center */}
        <MatchCard match={selectedMatch} question={question} answer={answer}
          loading={loading} error={error} userTier={userTier}
          onChange={setQuestion} onAsk={() => ask()} onPreset={ask} />

        {/* right */}
        <aside className="sqh-panel sqh-ask-panel">
          <AccountStatus tier={userTier} nickname="球友" />
          <AuthGate tier={userTier} requiredTier="paid">
            <div className="sqh-section-title"><Question size={16} weight="duotone" /><span>问答历史</span></div>
            {answer ? (
              <div style={{ fontSize: 12, color: '#6d725f', marginTop: 8 }}>
                最近：{question.slice(0, 30)}…<br />判断：{answer.judgment || '—'}
              </div>
            ) : (
              <p style={{ fontSize: 12, color: '#6d725f', marginTop: 8 }}>暂无记录，选择比赛开始提问</p>
            )}
            <div style={{ marginTop: 12, fontSize: 11, color: '#c9a86a' }}>研判结论不构成投注建议</div>
          </AuthGate>
        </aside>
      </section>
    </main>
  )
}

// ── MatchQuestionCard ──

function MatchCard({ match, question, answer, loading, error, userTier, onChange, onAsk, onPreset }: {
  match: FootballMatch; question: string; answer: FootballQuestionAnswer | null
  loading: boolean; error: string; userTier: UserTier
  onChange: (v: string) => void; onAsk: () => void; onPreset: (v: string) => void
}) {
  return (
    <section className="sqh-panel sqh-question-card">
      <div className="sqh-match-hero">
        <div className="sqh-hero-meta"><span>{match.league}</span><span>{match.kickoffAt}</span></div>
        <div className="sqh-teams"><strong>{match.homeTeam}</strong><span>VS</span><strong>{match.awayTeam}</strong></div>
        <p>{match.publicLean}</p>
      </div>
      <AuthGate tier={userTier} requiredTier="paid">
        <div className="sqh-ask-box">
          <div className="sqh-section-title"><Question size={16} weight="duotone" /><span>继续问这场比赛</span></div>
          <div className="sqh-input-row">
            <input value={question} onChange={e => onChange(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') onAsk() }}
              placeholder="例如：本场红黄牌风险是否偏高？" />
            <motion.button whileTap={{ scale: 0.96 }} onClick={onAsk}>
              {loading ? '判断中' : '提问'}<ArrowRight size={15} weight="bold" />
            </motion.button>
          </div>
          <div className="sqh-question-chips">
            {match.questions.map(item => (
              <button key={item.id} onClick={() => onPreset(item.prompt)}>{item.label}</button>
            ))}
          </div>
          {error && <div className="sqh-answer-error">{error}</div>}
          {loading && <div className="sqh-answer-loading"><i><b /></i><span>正在判断…</span></div>}
          {answer && (
            <motion.div className="sqh-answer" data-related={answer.related} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div className="sqh-answer-head">
                <strong>{answer.related ? `判断 · ${answer.confidence_level}` : '无法回答'}</strong>
                {answer.related && answer.judgment && <span>{answer.judgment}</span>}
              </div>
              <p>{answer.answer}</p>
              {answer.reasons.length > 0 && <ul>{answer.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
            </motion.div>
          )}
        </div>
      </AuthGate>
    </section>
  )
}
