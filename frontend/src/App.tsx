import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Clock, Question } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import {
  askFootballQuestion, createFootballOsintJob, fetchFixtures, getMe, loginUser, logoutUser, registerUser,
} from './shijieqiuhua/api'
import type { AuthUser } from './shijieqiuhua/api'
import { fixtureToMatch } from './shijieqiuhua/mockData'
import type { FootballMatch, FootballOsintJob, FootballQuestionAnswer } from './shijieqiuhua/types'
import AuthGate from './shijieqiuhua/components/AuthGate'
import type { UserTier } from './shijieqiuhua/components/AuthGate'
import AccountStatus from './shijieqiuhua/components/AccountStatus'
import EvidenceStrength from './shijieqiuhua/components/EvidenceStrength'
import PaymentUnlock from './shijieqiuhua/components/PaymentUnlock'
import AdminPanel from './shijieqiuhua/components/AdminPanel'
import './shijieqiuhua.css'

const FIXTURES_POLL_MS = 60_000

// Entitlement expires_at is stored UTC as "YYYY-MM-DD HH:MM:SS" (no tz). Parse
// it as a real timestamp instead of lexicographic string compare, which broke
// at the space-vs-'T' boundary against Date.toISOString().
function isExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return false // null = permanent
  const normalized = expiresAt.includes('T') ? expiresAt : expiresAt.replace(' ', 'T') + 'Z'
  const ts = Date.parse(normalized)
  if (Number.isNaN(ts)) return false // unparseable → treat as active, fail open
  return ts <= Date.now()
}

export default function App() {
  const [matches, setMatches] = useState<FootballMatch[]>([])
  const [fixturesLoading, setFixturesLoading] = useState(true)
  const [selectedId, setSelectedId] = useState('')
  const [question, setQuestion] = useState('上半场角球会不会偏多？')
  const [answer, setAnswer] = useState<FootballQuestionAnswer | null>(null)
  const [osintJob, setOsintJob] = useState<FootballOsintJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginUser_, setLoginUser_] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginEmail, setLoginEmail] = useState('')
  const [loginInvite, setLoginInvite] = useState('')
  const [loginMode, setLoginMode] = useState<'login' | 'register'>('login')
  const [authError, setAuthError] = useState('')

  useEffect(() => { getMe().then(setUser).finally(() => setAuthLoading(false)) }, [])

  useEffect(() => {
    let cancelled = false
    async function loadFixtures() {
      try {
        const fixtures = await fetchFixtures(3)
        if (cancelled) return
        if (fixtures.length > 0) {
          setMatches(fixtures.map(fixtureToMatch))
        }
      } catch {
        // keep current matches (or empty) on error
      } finally {
        if (!cancelled) setFixturesLoading(false)
      }
    }
    loadFixtures()
    const interval = setInterval(loadFixtures, FIXTURES_POLL_MS)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  useEffect(() => {
    if (matches.length === 0) {
      setSelectedId('')
      return
    }
    if (!matches.some(m => m.id === selectedId)) {
      setSelectedId(matches[0].id)
    }
  }, [matches, selectedId])

  const userTier: UserTier = useMemo(() => {
    if (!user) return 'guest'
    const hasPaid = user.entitlements?.some(e => e.type === 'full_analysis' && !isExpired(e.expires_at))
    return hasPaid ? 'paid' : 'free'
  }, [user])

  async function handleAuth() {
    setAuthError('')
    try {
      const u = loginMode === 'login'
        ? await loginUser(loginUser_, loginPass)
        : await registerUser(loginUser_, loginPass, loginInvite, loginEmail)
      setUser(u)
      setLoginUser_(''); setLoginPass(''); setLoginEmail(''); setLoginInvite('')
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : '认证失败')
    }
  }

  async function handleLogout() { await logoutUser(); setUser(null); setAnswer(null); setOsintJob(null); setError('') }

  const selectedMatch = useMemo(
    () => matches.find(m => m.id === selectedId) ?? (matches.length > 0 ? matches[0] : null),
    [matches, selectedId],
  )

  async function ask(next = question) {
    if (!selectedMatch) return
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
            {fixturesLoading ? (
              <span style={{ fontSize: 12, color: '#6d725f', padding: 8 }}>加载中…</span>
            ) : matches.length === 0 ? (
              <span style={{ fontSize: 12, color: '#6d725f', padding: 8 }}>暂无赛事</span>
            ) : (
              matches.map(m => (
                <button key={m.id} className="sqh-match-row" data-active={m.id === selectedId}
                  onClick={() => { setSelectedId(m.id); setAnswer(null); setError('') }}>
                  <span className="sqh-match-league">{m.league}</span>
                  <strong>{m.homeTeam} vs {m.awayTeam}</strong>
                  <span>{m.kickoffAt} · {m.publicLean}</span>
                </button>
              ))
            )}
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
              {userTier === 'free' && <PaymentUnlock user={user} onRedeemed={setUser} />}
              {user.role === 'admin' && <AdminPanel user={user} />}
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
                  <>
                    <input style={{ width: '100%', marginTop: 6, padding: '6px 8px', border: '1px solid #e1d7c6', borderRadius: 8, fontSize: 12 }}
                      placeholder="邮箱（选填）" value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') handleAuth() }} />
                    <input style={{ width: '100%', marginTop: 6, padding: '6px 8px', border: '1px solid #e1d7c6', borderRadius: 8, fontSize: 12 }}
                      placeholder="邀请码" value={loginInvite} onChange={e => setLoginInvite(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') handleAuth() }} />
                  </>
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
          <div style={{ marginTop: 12, fontSize: 11, color: '#c9a86a' }}>
            研判结论不构成投注建议 · 缺数据时明说，不编造倾向 · <a href="/terms.html" style={{color:'inherit'}}>用户协议</a> · <a href="/privacy.html" style={{color:'inherit'}}>隐私政策</a>
          </div>
        </aside>
      </section>
    </main>
  )
}

// ── MatchQuestionCard ──

function MatchCard({ match, question, answer, osintJob, loading, error, userTier, onChange, onAsk, onPreset }: {
  match: FootballMatch | null; question: string; answer: FootballQuestionAnswer | null
  osintJob: FootballOsintJob | null; loading: boolean; error: string; userTier: UserTier
  onChange: (v: string) => void; onAsk: () => void; onPreset: (v: string) => void
}) {
  if (!match) {
    return (
      <section className="sqh-panel sqh-question-card" style={{ display: 'grid', placeItems: 'center', minHeight: 300 }}>
        <p style={{ color: '#6d725f', fontSize: 14 }}>暂无赛事数据，请稍后再试</p>
      </section>
    )
  }
  return (
    <section className="sqh-panel sqh-question-card">
      <div className="sqh-match-hero">
        <div className="sqh-hero-meta"><span>{match.league}</span><span>{match.kickoffAt}</span></div>
        <div className="sqh-teams"><strong>{match.homeTeam}</strong><span>对阵</span><strong>{match.awayTeam}</strong></div>
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
        <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: osintJob.prediction.lean === 'info_insufficient' ? '#f1e4dd' : '#edf3e8', fontSize: 13, lineHeight: 1.6 }}>
          <strong>情报研判 · {osintJob.confidence?.level ?? '—'}</strong>
          <p style={{ margin: '4px 0 0' }}>{osintJob.prediction.summary}</p>
          {osintJob.prediction.lean === 'info_insufficient' && (
            <p style={{ margin: '6px 0 0', fontSize: 12, color: '#8a523f' }}>我们没编。这场缺关键数据，等开赛前 2 小时还会再扫一遍。</p>
          )}
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
