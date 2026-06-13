import type { UserTier } from './AuthGate'

interface Props { tier: UserTier; nickname?: string }

const LABELS: Record<UserTier, string> = { guest: '访客', free: '已注册', paid: '已付费' }

export default function AccountStatus({ tier, nickname }: Props) {
  return (
    <div className={`sqh-account-bar sqh-account-bar--${tier === 'paid' ? 'paid' : 'guest'}`}>
      <span className={`sqh-account-badge sqh-account-badge--${tier}`}>{LABELS[tier]}</span>
      {nickname && <span>{nickname}</span>}
      <span style={{ marginLeft: 'auto', fontSize: 11 }}>
        {tier === 'guest' && '邀请码注册'}
        {tier === 'free' && '待开通'}
        {tier === 'paid' && '完整功能'}
      </span>
    </div>
  )
}
