import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Clock, Question } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import {
  askFootballQuestion, createFootballOsintJob, getMe, loginUser, logoutUser, registerUser,
} from './shijieqiuhua/api'
import type { AuthUser } from './shijieqiuhua/api'
import { MATCHES } from './shijieqiuhua/mockData'
import type { FootballMatch, FootballOsintJob, FootballQuestionAnswer } from './shijieqiuhua/types'
import AuthGate from './shijieqiuhua/components/AuthGate'
import type { UserTier } from './shijieqiuhua/components/AuthGate'
import AccountStatus from './shijieqiuhua/components/AccountStatus'
import EvidenceStrength from './shijieqiuhua/components/EvidenceStrength'
import './shijieqiuhua.css'

export default function App() {
  const [selectedId, setSelectedId] = useState(MATCHES[0].id)
  const [question, setQuestion] = useState('上半场角球会不会偏多？')
  const [answer, setAnswer] = useState<FootballQuestionAnswer | null>(null)
  const [osintJob, setOsintJob] = useState<FootballOsintJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginUser_, setLoginUser_] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginInvite, setLoginInvite] = useState('')
  const [loginMode, setLoginMode] = useState<'login' | 'register'>('login')
  const [authError, setAuthError] = useState('')

  useEffect(() => { getMe().then(setUser).finally(() => setAuthLoading(false)) }, [])

  const userTier: UserTier = useMemo(() => {
    if (!user) return 'guest'
    const hasPaid = user.entitlements?.some(e => e.type === 'full_analysis'
      && (!e.expires_at || e.expires_at > new Date().toISOString()))
    return hasPaid ? 'paid' : 'free'
  }, [user])

  async function handleAuth() {
    setAuthError('')
    try {
      const u = loginMode === 'login'
        ? await loginUser(loginUser_, loginPass)
        : await registerUser(loginUser_, loginPass, loginInvite)
      setUser(u)
      setLoginUser_(''); setLoginPass(''); setLoginInvite('')
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : '认证失败')
    }
  }

  async function handleLogout() { await logoutUser(); setUser(null) }

  const selectedMatch = useMemo(
    () => MATCHES.find(m => m.id === selectedId) ?? MATCHES[0],
    [selectedId],
  )

  async function ask(next = question) {
    setQuestion(next)
    setLoading(true)
    setError('')
    setAnswer(null)
    setOsintJob(null)
    const request = {
      home_team: selectedMatch.homeTeam,
      away_team: selectedMatch.awayTeam,
      kickoff_at: selectedMatch.kickoffAt,
      competition: selectedMatch.league,
      question: next,
    }
    try {
      const [job, qa] = await Promise.all([
        createFootballOsintJob(request).catch(() => null),
        askFootballQuestion(request),
      ])
      setAnswer(qa)
      setOsintJob(job)
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
          osintJob={osintJob} loading={loading} error={error} userTier={userTier}
          onChange={setQuestion} onAsk={() => ask()} onPreset={ask} />

        {/* right */}
        <aside className="sqh-panel sqh-ask-panel">
          {authLoading ? (
            <span style={{ fontSize: 12, color: '#6d725f' }}>加载中…</span>
          ) : user ? (
            <>
              <AccountStatus tier={userTier} nickname={user.username} />
              <AuthGate tier={userTier} requiredTier="paid">
                <div className="sqh-section-title"><Question size={16} weight="duotone" /><span>问答历史</span></div>
                {answer ? (
                  <div style={{ fontSize: 12, color: '#6d725f', marginTop: 8 }}>
                    最近：{question.slice(0, 30)}…<br />判断：{answer.judgment || '—'}
                  </div>
                ) : (
                  <p style={{ fontSize: 12, color: '#6d725f', marginTop: 8 }}>暂无记录，选择比赛开始提问</p>
                )}
              </AuthGate>
              <button style={{ marginTop: 8, border: '1px solid #e3d8c7', borderRadius: 8, background: 'transparent', padding: '6px 12px', cursor: 'pointer', fontSize: 12 }} onClick={handleLogout}>退出</button>
            </>
          ) : (
            <div>
              <AccountStatus tier="guest" />
              <div style={{ marginTop: 12 }}>
                <div className="sqh-section-title"><span>{loginMode === 'login' ? '登录' : '注册'}</span></div>
                <input style={{ width: '100%', marginTop: 8, padding: '6px 8px', border: '1px solid #e1d7c6', borderRadius: 8, fontSize: 12 }}
                  placeholder="用户名" value={loginUser_} onChange={e => setLoginUser_(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleAuth() }} />
                <input style={{ width: '100%', marginTop: 6, padding: '6px 8px', border: '1px solid #e1d7c6', borderRadius: 8, fontSize: 12 }}
                  type="password" placeholder="密码" value={loginPass} onChange={e => setLoginPass(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleAuth() }} />
                {loginMode === 'register' && (
                  <input style={{ width: '100%', marginTop: 6, padding: '6px 8px', border: '1px solid #e1d7c6', borderRadius: 8, fontSize: 12 }}
                    placeholder="邀请码" value={loginInvite} onChange={e => setLoginInvite(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleAuth() }} />
                )}
                {authError && <div style={{ marginTop: 6, fontSize: 11, color: '#8a523f' }}>{authError}</div>}
                <button style={{ marginTop: 8, width: '100%', border: 0, borderRadius: 8, background: '#143c2d', color: '#f8f1df', padding: '8px', fontWeight: 900, cursor: 'pointer' }}
                  onClick={handleAuth}>{loginMode === 'login' ? '登录' : '注册'}</button>
                <button style={{ marginTop: 4, width: '100%', border: 0, borderRadius: 8, background: 'transparent', color: '#6d725f', padding: '6px', fontSize: 11, cursor: 'pointer' }}
                  onClick={() => { setLoginMode(loginMode === 'login' ? 'register' : 'login'); setAuthError('') }}>
                  {loginMode === 'login' ? '没有账号？注册' : '已有账号？登录'}
                </button>
              </div>
            </div>
          )}
          <div style={{ marginTop: 12, fontSize: 11, color: '#c9a86a' }}>研判结论不构成投注建议</div>
        </aside>
      </section>
    </main>
  )
}

// ── MatchQuestionCard ──

function MatchCard({ match, question, answer, osintJob, loading, error, userTier, onChange, onAsk, onPreset }: {
  match: FootballMatch; question: string; answer: FootballQuestionAnswer | null
  osintJob: FootballOsintJob | null; loading: boolean; error: string; userTier: UserTier
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

      {/* evidence — shown when full OSINT job data is available */}
      {osintJob && osintJob.evidence.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <EvidenceStrength evidence={osintJob.evidence} factors={osintJob.factors} />
        </div>
      )}

      {/* prediction summary — shown from OSINT job */}
      {osintJob?.prediction && (
        <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: '#edf3e8', fontSize: 13, lineHeight: 1.6 }}>
          <strong>OSINT 研判 · {osintJob.confidence?.level ?? '—'}</strong>
          <p style={{ margin: '4px 0 0' }}>{osintJob.prediction.summary}</p>
          {osintJob.prediction.drivers.length > 0 && (
            <span style={{ color: '#6d725f', fontSize: 11 }}>
              关键因子：{osintJob.prediction.drivers.join('、')}
            </span>
          )}
        </div>
      )}
    </section>
  )
}
