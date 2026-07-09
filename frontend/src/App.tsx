import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Clock, Eye, House, Question } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import {
  askFootballQuestion, compareMatches, createFootballOsintJob, fetchFixtures,
  fetchFootballOsintJob, fetchHistory, fetchHistoryDetail,
  getMe, loginUser, logoutUser, registerUser,
} from './shijieqiuhua/api'
import type { AuthUser } from './shijieqiuhua/api'
import { fixtureToMatch } from './shijieqiuhua/mockData'
import type { CompareItem, FootballMatch, FootballOsintJob, FootballOsintJobRequest, FootballQuestionAnswer, HistoryDetail, HistoryRecord } from './shijieqiuhua/types'
import AuthGate from './shijieqiuhua/components/AuthGate'
import type { UserTier } from './shijieqiuhua/components/AuthGate'
import AdminPanel from './shijieqiuhua/components/AdminPanel'
import ReportView from './shijieqiuhua/components/ReportView'
import PhaseTracker from './shijieqiuhua/components/PhaseTracker'
import PaywallModal from './shijieqiuhua/components/PaywallModal'
import LandingPage from './shijieqiuhua/components/LandingPage'
import AuthScreen from './shijieqiuhua/components/AuthScreen'
import type { AuthCredentials } from './shijieqiuhua/components/AuthScreen'
import AccountPanel from './shijieqiuhua/components/AccountPanel'
import type { HistoryItem } from './shijieqiuhua/components/AccountPanel'
import PostMatchReview from './shijieqiuhua/components/PostMatchReview'
import ComparePanel from './shijieqiuhua/components/ComparePanel'
import IdleHint from './shijieqiuhua/components/IdleHint'
import { useStagedProgress } from './shijieqiuhua/useStagedProgress'
import { dedupeHistoryRecords } from './shijieqiuhua/historyRecords'
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
  const [question, setQuestion] = useState('全场角球数预测是多少？')
  const [answer, setAnswer] = useState<FootballQuestionAnswer | null>(null)
  const [osintJob, setOsintJob] = useState<FootballOsintJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [showPaywall, setShowPaywall] = useState(false)
  const [fixtureFilter, setFixtureFilter] = useState('全部')
  const [view, setView] = useState<'landing' | 'auth' | 'app'>('landing')
  const [history, setHistory] = useState<HistoryItem[]>([])
  // v2 history mode
  const [historyMode, setHistoryMode] = useState(false)
  const [historyRecords, setHistoryRecords] = useState<HistoryRecord[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [selectedHistoryJobId, setSelectedHistoryJobId] = useState<string | null>(null)
  const [historyDetail, setHistoryDetail] = useState<HistoryDetail | null>(null)
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false)
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [compareResult, setCompareResult] = useState<CompareItem[] | null>(null)
  const [showCompare, setShowCompare] = useState(false)
  const [compareLoading, setCompareLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { staged, start: startStaged, finish: finishStaged, reset: resetStaged } = useStagedProgress()

  useEffect(() => { getMe().then(setUser).finally(() => setAuthLoading(false)) }, [])
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

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

  async function handleAuthSubmit(creds: AuthCredentials) {
    const u = authMode === 'login'
      ? await loginUser(creds.username, creds.password)
      : await registerUser(creds.username, creds.password, creds.invite, creds.email)
    setUser(u)
    setView('app')
  }

  async function handleLogout() {
    await logoutUser()
    setUser(null)
    setAnswer(null)
    setOsintJob(null)
    setError('')
    setHistoryMode(false)
    setHistoryRecords([])
    setSelectedHistoryJobId(null)
    setHistoryDetail(null)
    setCompareIds([])
    setCompareResult(null)
    setShowCompare(false)
  }

  function goAuth(mode: 'login' | 'register') { setAuthMode(mode); setView('auth') }

  function handlePaid(u: AuthUser) { setUser(u); setShowPaywall(false) }

  const selectedMatch = useMemo(
    () => matches.find(m => m.id === selectedId) ?? (matches.length > 0 ? matches[0] : null),
    [matches, selectedId],
  )

  const filteredMatches = useMemo(() => {
    if (fixtureFilter === '全部') return matches
    if (fixtureFilter === '进行中') return matches.filter(m => m.publicLean.includes('进行中'))
    if (fixtureFilter === '今日') return matches.filter(m => m.publicLean.includes('未开赛') || m.publicLean.includes('进行中'))
    return matches.filter(m => m.league.includes(fixtureFilter))
  }, [matches, fixtureFilter])

  const fixtureLeagues = useMemo(
    () => [...new Set(matches.map(m => m.league.split('·')[0].trim()))].slice(0, 4),
    [matches],
  )
  const displayedHistoryRecords = useMemo(
    () => dedupeHistoryRecords(historyRecords),
    [historyRecords],
  )

  function stopPoll() { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }

  async function enterHistoryMode() {
    setHistoryMode(true)
    setHistoryLoading(true)
    setSelectedHistoryJobId(null)
    setHistoryDetail(null)
    setCompareIds([])
    try { setHistoryRecords(await fetchHistory(30)) } catch { setHistoryRecords([]) }
    finally { setHistoryLoading(false) }
  }

  function exitHistoryMode() {
    setHistoryMode(false)
    setSelectedHistoryJobId(null)
    setHistoryDetail(null)
    setCompareIds([])
    setShowCompare(false)
  }

  async function selectHistoryJob(jobId: string) {
    setSelectedHistoryJobId(jobId)
    setHistoryDetail(null)
    setHistoryDetailLoading(true)
    try { setHistoryDetail(await fetchHistoryDetail(jobId)) } catch { setHistoryDetail(null) }
    finally { setHistoryDetailLoading(false) }
  }

  function toggleCompareId(jobId: string) {
    if (userTier !== 'paid') {
      setShowPaywall(true)
      return
    }
    setCompareIds(prev =>
      prev.includes(jobId) ? prev.filter(id => id !== jobId) : prev.length < 3 ? [...prev, jobId] : prev
    )
  }

  async function handleCompare() {
    if (compareIds.length < 2) return
    if (userTier !== 'paid') {
      setShowPaywall(true)
      return
    }
    setCompareLoading(true)
    setShowCompare(true)
    try { setCompareResult(await compareMatches(compareIds)) } catch { setCompareResult([]) }
    finally { setCompareLoading(false) }
  }

  async function ask(next = question) {
    if (!selectedMatch) return
    setQuestion(next)
    setLoading(true)
    setError('')
    setAnswer(null)
    setOsintJob(null)
    stopPoll()
    startStaged()
    const request: FootballOsintJobRequest = {
      home_team: selectedMatch.homeTeam,
      away_team: selectedMatch.awayTeam,
      kickoff_at: selectedMatch.kickoffAt,
      competition: selectedMatch.league,
      question: next,
      provider: selectedMatch.provider,
      provider_match_id: selectedMatch.provider_match_id,
      home_provider_id: selectedMatch.home_provider_id,
      away_provider_id: selectedMatch.away_provider_id,
    }
    try {
      const [job, qa] = await Promise.all([
        createFootballOsintJob(request).catch(() => null),
        askFootballQuestion(request),
      ])
      setAnswer(qa)
      if (qa.related) {
        setHistory(h => [{
          question: next,
          match: `${selectedMatch.homeTeam} vs ${selectedMatch.awayTeam}`,
          level: qa.confidence_level,
          at: '刚刚',
        }, ...h].slice(0, 6))
      }
      if (!job) { resetStaged(); setLoading(false); return }
      // If job already terminal, snap progress to done and show the report.
      if (job.phase === 'done' || job.status === 'completed' || job.status === 'failed') {
        finishStaged()
        setOsintJob(job)
        setLoading(false)
        return
      }
      // Defensive: if the backend ever returns a non-terminal job, poll for it.
      setOsintJob(job)
      const jobId = job.job_id
      pollRef.current = setInterval(async () => {
        try {
          const updated = await fetchFootballOsintJob(jobId)
          setOsintJob(updated)
          if (updated.phase === 'done' || updated.status === 'completed' || updated.status === 'failed') {
            stopPoll()
            finishStaged()
            setLoading(false)
          }
        } catch {
          stopPoll()
          resetStaged()
          setLoading(false)
        }
      }, 2000)
    } catch (e) {
      resetStaged()
      setError(e instanceof Error ? e.message : '问题处理失败')
      setLoading(false)
    }
  }

  if (view === 'landing') {
    return (
      <LandingPage
        onEnter={() => setView('app')}
        onRegister={() => goAuth('register')}
        onLogin={() => goAuth('login')}
      />
    )
  }

  if (view === 'auth') {
    return (
      <AuthScreen
        mode={authMode}
        onModeChange={setAuthMode}
        onSubmit={handleAuthSubmit}
        onBack={() => setView('landing')}
      />
    )
  }

  return (
    <main className="sqh-app">
      <header className="sqh-topbar">
        <div className="sqh-brand sqh-brand--clickable" onClick={() => setView('landing')}
          role="button" tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') setView('landing') }}>
          <div className="sqh-mark">世</div>
          <div><h1>世界球花</h1><p>足球情报问答</p></div>
        </div>
        <button className="btn btn-quiet btn-sm" onClick={() => setView('landing')}>
          <House size={15} weight="bold" /> 首页
        </button>
      </header>

      <section className="sqh-shell">
        {/* left */}
        <aside className="sqh-panel sqh-match-rail" aria-label="赛事列表">
          <div className="sqh-rail-hd">
            <div className="sqh-section-title"><Clock size={16} weight="duotone" /><span>{historyMode ? '历史回顾' : '赛程'}</span></div>
            <div className="sqh-rail-count mono">{historyMode ? `${displayedHistoryRecords.length} 场` : `${matches.length} 场`}</div>
          </div>
          {user && (
            <div className="sqh-rail-mode">
              <button className={`sqh-rail-mode-btn${!historyMode ? ' sqh-rail-mode-btn--on' : ''}`}
                onClick={exitHistoryMode}>赛程</button>
              <button className={`sqh-rail-mode-btn${historyMode ? ' sqh-rail-mode-btn--on' : ''}`}
                onClick={enterHistoryMode}>历史</button>
            </div>
          )}

          {historyMode ? (
            <div className="sqh-rail-list">
              {historyLoading ? (
                <span style={{ fontSize: 12, color: '#6d725f', padding: 8 }}>加载中…</span>
              ) : displayedHistoryRecords.length === 0 ? (
                <span style={{ fontSize: 12, color: '#6d725f', padding: 8 }}>暂无已结算记录</span>
              ) : (
                displayedHistoryRecords.map(r => (
                  <div key={r.job_id} className="sqh-hist-check-row">
                    {userTier === 'paid' && (
                      <input type="checkbox" className="sqh-hist-checkbox"
                        checked={compareIds.includes(r.job_id)}
                        onChange={() => toggleCompareId(r.job_id)} />
                    )}
                    <button className="sqh-hist-record" data-active={r.job_id === selectedHistoryJobId}
                      onClick={() => selectHistoryJob(r.job_id)}>
                      <div className="sqh-hist-record-teams">{r.home_team} vs {r.away_team}</div>
                      <div className="sqh-hist-record-meta">
                        <span>{r.kickoff_at}</span>
                        <span>{r.competition}</span>
                      </div>
                      <div className="sqh-hist-record-badges">
                        {r.predicted_lean === 'info_insufficient' ? (
                          <span className="sqh-hist-badge">未计入</span>
                        ) : (
                          <>
                            <span className={`sqh-hist-badge ${r.lean_correct ? 'sqh-hist-badge--hit' : 'sqh-hist-badge--miss'}`}>
                              {r.lean_correct ? '方向✓' : '方向✗'}
                            </span>
                            <span className={`sqh-hist-badge ${r.scoreline_hit ? 'sqh-hist-badge--hit' : 'sqh-hist-badge--miss'}`}>
                              {r.actual_home_score}-{r.actual_away_score}
                            </span>
                          </>
                        )}
                      </div>
                    </button>
                  </div>
                ))
              )}
              {compareIds.length >= 2 && (
                <div className="sqh-hist-compare-bar">
                  <button className="sqh-hist-compare-btn" onClick={handleCompare}>
                    对比 {compareIds.length} 场
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="sqh-rail-filters">
                {['全部', '今日', '进行中', ...fixtureLeagues].map(f => (
                  <button key={f} className={`sqh-filter-chip${fixtureFilter === f ? ' sqh-filter-chip--on' : ''}`}
                    onClick={() => setFixtureFilter(f)}>{f}</button>
                ))}
              </div>
              <div className="sqh-rail-list">
                {fixturesLoading ? (
                  <span style={{ fontSize: 12, color: '#6d725f', padding: 8 }}>加载中…</span>
                ) : filteredMatches.length === 0 ? (
                  <span style={{ fontSize: 12, color: '#6d725f', padding: 8 }}>暂无赛事</span>
                ) : (
                  filteredMatches.map(m => {
                    const isLive = m.publicLean.startsWith('进行中')
                    return (
                      <button key={m.id} className="sqh-fixture" data-active={m.id === selectedId}
                        onClick={() => { stopPoll(); resetStaged(); setSelectedId(m.id); setAnswer(null); setOsintJob(null); setError(''); setLoading(false) }}>
                        <div className="sqh-fixture-top">
                          <span className="sqh-fixture-league">{m.league}</span>
                          {isLive && <span className="sqh-fixture-live">LIVE</span>}
                        </div>
                        <div className="sqh-fixture-teams">
                          <span>{m.homeTeam}</span>
                          <span className="sqh-fixture-vs">VS</span>
                          <span>{m.awayTeam}</span>
                        </div>
                        <div className="sqh-fixture-foot">
                          <span className={`sqh-status-dot${isLive ? ' sqh-status-dot--live' : ''}`} />
                          <span>{m.kickoffAt} · {m.publicLean}</span>
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </>
          )}
        </aside>

        {/* center */}
        {historyMode ? (
          <section className="sqh-panel" style={{ flex: 1, overflowY: 'auto' }}>
            <PostMatchReview
              detail={historyDetail}
              loading={historyDetailLoading}
              userTier={userTier}
              onUpgrade={() => setShowPaywall(true)}
            />
            {!historyDetailLoading && !historyDetail && (
              <div className="sqh-idle">
                <div className="sqh-idle-ic"><Eye size={24} weight="duotone" /></div>
                <p className="sqh-idle-title">选择左侧比赛查看回顾</p>
                <p className="sqh-idle-text">勾选 2–3 场可横向对比研判摘要。</p>
              </div>
            )}
          </section>
        ) : (
          <MatchCard match={selectedMatch} question={question} answer={answer}
            osintJob={osintJob} loading={loading} error={error} userTier={userTier}
            staged={staged}
            onChange={setQuestion} onAsk={() => ask()} onPreset={ask}
            onUpgrade={() => setShowPaywall(true)} />
        )}

        {/* right */}
        <aside className="sqh-panel sqh-ask-panel">
          {authLoading ? (
            <span style={{ fontSize: 12, color: '#6d725f' }}>加载中…</span>
          ) : (
            <>
              <AccountPanel
                user={user}
                tier={userTier}
                history={history}
                onLogin={() => goAuth('login')}
                onRegister={() => goAuth('register')}
                onUnlock={() => setShowPaywall(true)}
                onLogout={handleLogout}
              />
              {user?.role === 'admin' && <AdminPanel user={user} />}
            </>
          )}
        </aside>
      </section>

      {showPaywall && (
        <PaywallModal user={user} onClose={() => setShowPaywall(false)} onPaid={handlePaid} />
      )}
      {showCompare && compareResult && (
        <ComparePanel
          results={compareResult}
          loading={compareLoading}
          onClose={() => setShowCompare(false)}
        />
      )}
    </main>
  )
}

// Compute "T-Nh" countdown only from a strict ISO timestamp. The fixtures API
// returns pre-formatted display strings like "06-18 07:00" (no year/timezone),
// which Date.parse silently mis-reads as year 2001 → a bogus "进行中". Require a
// full ISO datetime so we never render a fabricated/garbage countdown.
function kickoffCountdown(kickoffAt: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(kickoffAt)) return null
  const ts = Date.parse(kickoffAt)
  if (Number.isNaN(ts)) return null
  const diffH = (ts - Date.now()) / 3_600_000
  if (diffH <= 0) return '进行中'
  if (diffH < 1) return `T-${Math.round(diffH * 60)}min`
  if (diffH < 72) return `T-${Math.round(diffH)}h`
  return `T-${Math.round(diffH / 24)}d`
}

// ── Structured Report Renderer ──

const SECTION_META: Record<string, { icon: string; color: string; bg: string }> = {
  '方向研判': { icon: '🎯', color: '#143c2d', bg: '#edf3e8' },
  '置信度':    { icon: '📊', color: '#1a3a5c', bg: '#eaf0f8' },
  '确认事实':  { icon: '✓', color: '#2d5016', bg: '#edf3e8' },
  '替代解释':  { icon: '⚠', color: '#8a6d3b', bg: '#faf7e6' },
  '数据缺口':  { icon: '○', color: '#6d725f', bg: '#f5f2ed' },
}

interface Section { title: string; body: string }

function StructuredReport({ text }: { text: string }) {
  if (!text) return null

  // Strip intro fluff.
  const cleaned = text.replace(/^好的[，,]\s*基于[^。\n]*。?\n*/s, '').replace(/^---+\s*\n*/m, '')

  // When the LLM used 【Section】 markers, render as structured cards.
  if (cleaned.includes('【')) {
    const sections = parseSections(cleaned)
    return (
      <div className="sqh-structured-report">
        {sections.map((sec, i) => {
          const meta = SECTION_META[sec.title]
          if (!meta) return <p key={i} style={{ whiteSpace: 'pre-wrap' }}>{sec.body}</p>
          const bodyHtml = fmtBody(sec.body, sec.title)
          return (
            <div key={i} className="sqh-report-section" style={{ background: meta.bg, marginTop: i === 0 ? 8 : 10 }}>
              <div className="sqh-report-section-hd" style={{ color: meta.color }}>
                <span>{meta.icon}</span><strong>{sec.title}</strong>
                {sec.title === '置信度' && <ConfidenceBadge body={sec.body} />}
              </div>
              <div className="sqh-report-section-bd" dangerouslySetInnerHTML={{ __html: bodyHtml }} />
            </div>
          )
        })}
      </div>
    )
  }

  // Conversational / unstructured answer — still apply basic formatting.
  const html = fmtBody(cleaned, '')
  return <div className="sqh-structured-report" style={{ marginTop: 8, fontSize: 13, lineHeight: 1.7, color: '#3d4038' }}
    dangerouslySetInnerHTML={{ __html: html }} />
}

function parseSections(text: string): Section[] {
  const sections: Section[] = []
  const re = /【([^】]+)】/g
  let match: RegExpExecArray | null
  let lastIdx = 0
  let lastTitle = ''

  while ((match = re.exec(text)) !== null) {
    if (lastTitle) {
      sections.push({ title: lastTitle, body: text.slice(lastIdx, match.index).trim() })
    }
    lastTitle = match[1]
    lastIdx = match.index + match[0].length
  }
  if (lastTitle) {
    sections.push({ title: lastTitle, body: text.slice(lastIdx).trim() })
  }
  return sections
}

function fmtBody(body: string, section: string): string {
  // Preserve bold markers and list numbering.
  let html = body
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/^(\d+)[\.\、]\s*/gm, '<span class="sqh-list-num">$1.</span> ')
    .replace(/\n/g, '<br/>')

  // Highlight source citations (e.g., [来源：goal.com] or [sportsmole.co.uk])
  html = html.replace(/\[(来源[：:][^\]]+|[^\s\]]+\.[a-z]{2,}[^\]]*)\]/g,
    '<span class="sqh-source-tag">$1</span>')

  // Confidence level → colored badge (always on — works both in section-mode and conversational)
  html = html.replace(/\b(L[1-5])\b/g, '<span class="sqh-conf-badge sqh-conf-$1">$1</span>')

  return html
}

function ConfidenceBadge({ body }: { body: string }) {
  const m = body.match(/L[1-5]/)
  if (!m) return null
  const level = m[0]
  const labels: Record<string, string> = { L1: '确认', L2: '高可信', L3: '中可信', L4: '推测', L5: '无效' }
  return <span className={`sqh-conf-badge sqh-conf-${level}`}>{level} · {labels[level] || ''}</span>
}

// ── MatchQuestionCard ──

function MatchCard({ match, question, answer, osintJob, loading, error, userTier, staged, onChange, onAsk, onPreset, onUpgrade }: {
  match: FootballMatch | null; question: string; answer: FootballQuestionAnswer | null
  osintJob: FootballOsintJob | null; loading: boolean; error: string; userTier: UserTier
  staged: { phase: string; progress: number }
  onChange: (v: string) => void; onAsk: () => void; onPreset: (v: string) => void
  onUpgrade: () => void
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
        <div className="sqh-hero-foot">
          <span className="sqh-hero-pill"><Eye size={13} weight="duotone" />公开倾向 · {match.publicLean}</span>
          {(() => {
            const countdown = kickoffCountdown(match.kickoffIso)
            return countdown
              ? <span className="sqh-hero-stat"><b className="mono">{countdown}</b><span>距开赛</span></span>
              : null
          })()}
        </div>
      </div>
      <AuthGate tier={userTier} requiredTier="paid">
        <div className="sqh-ask-box">
          <div className="sqh-section-title"><Question size={16} weight="duotone" /><span>继续问这场比赛</span></div>
          <div className="sqh-input-row">
            <input value={question} onChange={e => onChange(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') onAsk() }}
              placeholder="例如：全场红黄牌的预测数量是多少？" />
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
          {!loading && !answer && !osintJob && <IdleHint />}
          {answer && (
            <motion.div className="sqh-answer" data-related={answer.related} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div className="sqh-answer-head">
                <strong>{answer.related ? `判断 · ${answer.confidence_level}` : '无法回答'}</strong>
                {answer.related && answer.judgment && <span>{answer.judgment}</span>}
              </div>
              <StructuredReport text={answer.answer} />
              {answer.reasons.length > 0 && <ul>{answer.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
            </motion.div>
          )}
        </div>
      </AuthGate>

      {/* live progress — staged phase animation while the synchronous job runs */}
      {loading && (
        <PhaseTracker phase={staged.phase} progress={staged.progress} />
      )}

      {/* evidence — shown when full OSINT job data is available */}
      <ReportView osintJob={osintJob} userTier={userTier} onUpgrade={onUpgrade} />
    </section>
  )
}
