import { Crown, FileText, Key } from '@phosphor-icons/react'
import type { AuthUser } from '../api'
import { PLANS } from '../plans'
import type { UserTier } from './AuthGate'

const PAID_PLAN = PLANS.find(p => p.id === 'paid')!

export interface HistoryItem {
  question: string
  match: string
  level: string
  at: string
}

interface AccountPanelProps {
  user: AuthUser | null
  tier: UserTier
  history: HistoryItem[]
  onLogin: () => void
  onRegister: () => void
  onUnlock: () => void
  onLogout: () => void
}

const TIER_LABEL: Record<UserTier, string> = { guest: '访客', free: '免费会员', paid: '情报通' }
const CONF_LABELS: Record<string, string> = { L1: '确认', L2: '高可信', L3: '中可信', L4: '推测' }

const UNLOCK_FEATURES = [
  '无限次完整研判',
  '因子权重与贝叶斯轨迹',
  '开赛前自动复扫提醒',
  '导出研判报告',
]

function TierBadge({ tier }: { tier: UserTier }) {
  return <span className={`sqh-tier-badge sqh-tier-badge--${tier}`}>{TIER_LABEL[tier]}</span>
}

function paidExpiry(user: AuthUser | null): string | null {
  const ent = user?.entitlements?.find(e => e.type === 'full_analysis')
  if (!ent) return null
  return ent.expires_at ? ent.expires_at.slice(0, 10) : '长期有效'
}

export default function AccountPanel({
  user, tier, history, onLogin, onRegister, onUnlock, onLogout,
}: AccountPanelProps) {
  return (
    <div className="sqh-acct">
      {user ? (
        <div className="sqh-acct-card">
          <div className="sqh-acct-head">
            <span className="sqh-acct-avatar">{user.username.slice(0, 1).toUpperCase()}</span>
            <div className="grow">
              <div className="sqh-acct-name">{user.username}</div>
              <div style={{ marginTop: 3 }}><TierBadge tier={tier} /></div>
            </div>
            <button className="btn btn-quiet btn-sm" onClick={onLogout}>退出</button>
          </div>
          <div className="hr" style={{ margin: '13px 0' }} />
          {tier === 'paid' ? (
            <div className="sqh-quota">
              <span className="sqh-quota-ring sqh-quota-ring--full"><i>∞</i></span>
              <div>
                <div className="sqh-quota-title">无限研判</div>
                <div className="sqh-quota-sub">会员有效期至 {paidExpiry(user) ?? '—'}</div>
              </div>
            </div>
          ) : (
            <div className="sqh-quota">
              <span className="sqh-quota-ring"><i>1</i></span>
              <div className="grow">
                <div className="sqh-quota-title">每日免费额度</div>
                <div className="sqh-quota-sub">每日 1 次完整研判 · 次日 00:00 重置</div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="sqh-acct-card">
          <div className="sqh-acct-name">访客模式</div>
          <p className="sqh-acct-guest-lead">
            注册后每天可免费完整研判 1 次，并查看证据链与置信度。
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary btn-sm grow" onClick={onRegister}>
              <Key size={15} weight="bold" />邀请码注册
            </button>
            <button className="btn btn-ghost btn-sm" onClick={onLogin}>登录</button>
          </div>
        </div>
      )}

      {tier !== 'paid' && (
        <div className="sqh-promo">
          <h3><Crown size={18} weight="duotone" />情报通会员</h3>
          <ul className="sqh-promo-feat">
            {UNLOCK_FEATURES.map(f => <li key={f}>{f}</li>)}
          </ul>
          <button className="btn btn-gold btn-block" onClick={onUnlock}>¥{PAID_PLAN.price}/月 · 解锁完整研判</button>
        </div>
      )}

      <div className="sqh-hist">
        <div className="sqh-section-title"><FileText size={15} weight="duotone" /><span>研判历史</span></div>
        <div style={{ marginTop: 8 }}>
          {history.length === 0 ? (
            <p className="sqh-hist-empty">暂无记录，选一场比赛开始研判。</p>
          ) : history.map((h, i) => (
            <div className="sqh-hist-item" key={i}>
              <span className="sqh-hist-q">{h.question}</span>
              <span className="sqh-hist-meta">
                <span className={`sqh-cbadge sqh-cbadge--${h.level}`}>{CONF_LABELS[h.level] || ''}</span>
                {h.match} · {h.at}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grow" />
      <div className="sqh-acct-foot">
        研判结论不构成投注建议 · 缺数据时明说，不编造倾向<br />
        <a href="/terms.html">用户协议</a> · <a href="/privacy.html">隐私政策</a>
      </div>
    </div>
  )
}
