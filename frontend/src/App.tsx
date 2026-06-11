import { useMemo, useState } from 'react'
import {
  ArrowRight,
  CheckCircle,
  Clock,
  Copy,
  CreditCard,
  FileText,
  LockKey,
  Question,
  ShieldCheck,
  Sparkle,
  Ticket,
  UserCircle,
  WarningCircle,
} from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import {
  canUseFullAnalysis,
  createInvitation,
  createRegisteredUser,
  redeemActivationCode,
  validateInviteCode,
} from './shijieqiuhua/access'
import { ACTIVATION_CODES, MATCHES } from './shijieqiuhua/mockData'
import type { AccessMode, ActivationCode, EvidenceItem, FootballMatch, UserProfile } from './shijieqiuhua/types'
import './shijieqiuhua.css'

const ACCESS_LABEL: Record<AccessMode, string> = {
  public: '公开预览',
  registered_unpaid: '待开通',
  paid: '完整权限',
}

const EVIDENCE_LABEL: Record<EvidenceItem['strength'], string> = {
  strong: '强证据',
  weak: '弱信号',
  insufficient: '样本不足',
}

function pct(value: number) {
  return `${Math.round(value)}%`
}

export default function App() {
  const [selectedId, setSelectedId] = useState(MATCHES[0].id)
  const [user, setUser] = useState<UserProfile | null>(null)
  const [activationCodes, setActivationCodes] = useState<ActivationCode[]>(ACTIVATION_CODES)
  const [inviteCode, setInviteCode] = useState('QH-2026-SEED')
  const [registerName, setRegisterName] = useState('林观球')
  const [activationCode, setActivationCode] = useState('PAY-2026-FULL')
  const [accountMessage, setAccountMessage] = useState('')
  const [generatedInvite, setGeneratedInvite] = useState('')
  const [question, setQuestion] = useState('上半场角球会不会偏多？')
  const [answer, setAnswer] = useState('')

  const selectedMatch = useMemo(
    () => MATCHES.find(match => match.id === selectedId) ?? MATCHES[0],
    [selectedId],
  )
  const accessMode: AccessMode = user?.status ?? 'public'
  const hasFullAccess = canUseFullAnalysis(user)

  function registerWithInvite() {
    const validation = validateInviteCode(inviteCode)
    if (!validation.ok) {
      setAccountMessage(validation.reason)
      return
    }
    const nextUser = createRegisteredUser(registerName, validation.code)
    setUser(nextUser)
    setAccountMessage('注册成功。兑换付费码后即可查看完整分析。')
  }

  function redeemCode() {
    const result = redeemActivationCode(user, activationCode, activationCodes)
    setActivationCodes(result.codes)
    if (!result.ok) {
      setAccountMessage(result.reason)
      return
    }
    setUser(result.user)
    setAccountMessage('完整功能已开通。')
  }

  function generateInvite() {
    const result = createInvitation(user)
    if (!result.ok) {
      setAccountMessage(result.reason)
      return
    }
    setGeneratedInvite(result.code)
    setAccountMessage('邀请码已生成，可复制链接或生成小程序码。')
  }

  function askMatchQuestion(nextQuestion = question) {
    setQuestion(nextQuestion)
    if (!hasFullAccess) {
      setAnswer('')
      setAccountMessage('使用邀请码注册并开通后，可以继续追问半场、红黄牌、角球和进球数。')
      return
    }
    const risk = selectedMatch.riskFlags[0]
    setAnswer(`${nextQuestion} 当前判断：${selectedMatch.prediction.summary} 主要风险是${risk}。证据强度需要按强证据、弱信号和样本不足分开阅读。`)
  }

  return (
    <main className="sqh-app">
      <header className="sqh-topbar">
        <div className="sqh-brand">
          <div className="sqh-mark">世</div>
          <div>
            <h1>世界球花</h1>
            <p>足球情报问答 · 邀请制访问</p>
          </div>
        </div>
        <div className="sqh-status-pill" data-mode={accessMode}>
          <ShieldCheck size={16} weight="duotone" />
          <span>{ACCESS_LABEL[accessMode]}</span>
        </div>
      </header>

      <section className="sqh-shell">
        <aside className="sqh-match-rail" aria-label="赛事列表">
          <div className="sqh-section-title">
            <Clock size={16} weight="duotone" />
            <span>今日赛事</span>
          </div>
          <div className="sqh-match-list">
            {MATCHES.map(match => (
              <button
                key={match.id}
                className="sqh-match-row"
                data-active={match.id === selectedId}
                onClick={() => {
                  setSelectedId(match.id)
                  setAnswer('')
                }}
              >
                <span className="sqh-match-league">{match.league}</span>
                <strong>{match.homeTeam} vs {match.awayTeam}</strong>
                <span>{match.kickoffAt} · {match.publicLean}</span>
              </button>
            ))}
          </div>
          <div className="sqh-rail-note">
            <LockKey size={16} weight="duotone" />
            <span>未开通时仅展示简单胜负倾向。</span>
          </div>
        </aside>

        <MatchQuestionCard
          match={selectedMatch}
          question={question}
          answer={answer}
          hasFullAccess={hasFullAccess}
          onQuestionChange={setQuestion}
          onAsk={() => askMatchQuestion()}
          onPreset={askMatchQuestion}
        />

        <aside className="sqh-account-panel" aria-label="账号与权限">
          <AccountPanel
            user={user}
            accessMode={accessMode}
            inviteCode={inviteCode}
            registerName={registerName}
            activationCode={activationCode}
            accountMessage={accountMessage}
            generatedInvite={generatedInvite}
            onInviteCodeChange={setInviteCode}
            onRegisterNameChange={setRegisterName}
            onActivationCodeChange={setActivationCode}
            onRegister={registerWithInvite}
            onRedeem={redeemCode}
            onGenerateInvite={generateInvite}
            onReset={() => {
              setUser(null)
              setGeneratedInvite('')
              setAnswer('')
              setAccountMessage('已切换回公开预览。')
            }}
          />
        </aside>
      </section>
    </main>
  )
}

function MatchQuestionCard({
  match,
  question,
  answer,
  hasFullAccess,
  onQuestionChange,
  onAsk,
  onPreset,
}: {
  match: FootballMatch
  question: string
  answer: string
  hasFullAccess: boolean
  onQuestionChange: (value: string) => void
  onAsk: () => void
  onPreset: (value: string) => void
}) {
  const ringStyle = { '--confidence': `${match.prediction.confidence * 3.6}deg` } as React.CSSProperties

  return (
    <section className="sqh-question-card">
      <div className="sqh-match-hero">
        <div className="sqh-hero-meta">
          <span>{match.league}</span>
          <span>{match.kickoffAt}</span>
        </div>
        <div className="sqh-teams">
          <strong>{match.homeTeam}</strong>
          <span>VS</span>
          <strong>{match.awayTeam}</strong>
        </div>
        <div className="sqh-prediction-grid">
          <div className="sqh-confidence-ring" style={ringStyle}>
            <span>{match.prediction.confidence}</span>
            <small>{match.prediction.rating}</small>
          </div>
          <div className="sqh-bars">
            <ProbabilityBar label="主胜" value={match.prediction.home} />
            <ProbabilityBar label="平局" value={match.prediction.draw} />
            <ProbabilityBar label="客胜" value={match.prediction.away} />
          </div>
        </div>
        <p>{hasFullAccess ? match.prediction.summary : match.publicLean}</p>
      </div>

      <div className="sqh-ask-box">
        <div className="sqh-section-title">
          <Question size={16} weight="duotone" />
          <span>继续问这场比赛</span>
        </div>
        <div className="sqh-input-row">
          <input
            value={question}
            onChange={event => onQuestionChange(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') onAsk()
            }}
            placeholder="例如：本场红黄牌风险是否偏高？"
          />
          <motion.button whileTap={{ scale: 0.96 }} onClick={onAsk}>
            追问
            <ArrowRight size={15} weight="bold" />
          </motion.button>
        </div>
        <div className="sqh-question-chips">
          {match.questions.map(item => (
            <button key={item.id} onClick={() => onPreset(item.prompt)}>
              {item.label}
            </button>
          ))}
        </div>
        {!hasFullAccess && (
          <div className="sqh-locked-callout">
            <LockKey size={18} weight="duotone" />
            <span>使用邀请码注册并开通后，才能查看角球、红黄牌、半场和完整证据。</span>
          </div>
        )}
        {answer && (
          <motion.div className="sqh-answer" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            {answer}
          </motion.div>
        )}
      </div>

      <div className="sqh-evidence-grid">
        {match.evidence.map(item => (
          <article key={item.id} className="sqh-evidence" data-strength={item.strength} data-locked={!hasFullAccess}>
            <span>{EVIDENCE_LABEL[item.strength]}</span>
            <strong>{hasFullAccess ? item.title : '开通后查看完整证据'}</strong>
            <small>{hasFullAccess ? item.source : '公开预览仅展示方向倾向'}</small>
          </article>
        ))}
      </div>

      <div className="sqh-report-strip">
        <FileText size={18} weight="duotone" />
        <div>
          <strong>赛前报告</strong>
          <span>{hasFullAccess ? '可保存问答、生成报告并同步到 Web 与小程序。' : '开通后解锁报告保存、收藏和订阅提醒。'}</span>
        </div>
      </div>
    </section>
  )
}

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  return (
    <label className="sqh-probability">
      <span>{label}</span>
      <i><b style={{ width: pct(value) }} /></i>
      <em>{pct(value)}</em>
    </label>
  )
}

function AccountPanel({
  user,
  accessMode,
  inviteCode,
  registerName,
  activationCode,
  accountMessage,
  generatedInvite,
  onInviteCodeChange,
  onRegisterNameChange,
  onActivationCodeChange,
  onRegister,
  onRedeem,
  onGenerateInvite,
  onReset,
}: {
  user: UserProfile | null
  accessMode: AccessMode
  inviteCode: string
  registerName: string
  activationCode: string
  accountMessage: string
  generatedInvite: string
  onInviteCodeChange: (value: string) => void
  onRegisterNameChange: (value: string) => void
  onActivationCodeChange: (value: string) => void
  onRegister: () => void
  onRedeem: () => void
  onGenerateInvite: () => void
  onReset: () => void
}) {
  return (
    <>
      <div className="sqh-account-card">
        <div className="sqh-section-title">
          <UserCircle size={16} weight="duotone" />
          <span>账号状态</span>
        </div>
        <div className="sqh-user-state" data-mode={accessMode}>
          <strong>{user?.name ?? '未注册访客'}</strong>
          <span>{ACCESS_LABEL[accessMode]}</span>
        </div>
        {user && <p className="sqh-muted">邀请码：{user.inviteCodeUsed}</p>}
        <button className="sqh-text-button" onClick={onReset}>切换公开预览</button>
      </div>

      <div className="sqh-account-card">
        <div className="sqh-section-title">
          <Ticket size={16} weight="duotone" />
          <span>邀请码注册</span>
        </div>
        <input value={registerName} onChange={event => onRegisterNameChange(event.target.value)} aria-label="用户名" />
        <input value={inviteCode} onChange={event => onInviteCodeChange(event.target.value)} aria-label="邀请码" />
        <button className="sqh-primary-action" onClick={onRegister}>
          使用邀请码注册
        </button>
      </div>

      <div className="sqh-account-card">
        <div className="sqh-section-title">
          <CreditCard size={16} weight="duotone" />
          <span>开通完整功能</span>
        </div>
        <input value={activationCode} onChange={event => onActivationCodeChange(event.target.value)} aria-label="付费码" />
        <button className="sqh-primary-action" onClick={onRedeem}>
          兑换付费码
        </button>
        <p className="sqh-muted">真实支付接入后，以服务端支付回调或兑换成功为准。</p>
      </div>

      <div className="sqh-account-card">
        <div className="sqh-section-title">
          <Sparkle size={16} weight="duotone" />
          <span>邀请新用户</span>
        </div>
        <button className="sqh-primary-action" onClick={onGenerateInvite}>
          生成邀请链接
        </button>
        {generatedInvite && (
          <div className="sqh-invite-code">
            <Copy size={15} weight="duotone" />
            <span>https://shijieqiuhua.example/invite/{generatedInvite}</span>
          </div>
        )}
      </div>

      {accountMessage && (
        <div className="sqh-message">
          {accessMode === 'paid' ? <CheckCircle size={17} weight="duotone" /> : <WarningCircle size={17} weight="duotone" />}
          <span>{accountMessage}</span>
        </div>
      )}
    </>
  )
}
