import type { ReactNode } from 'react'

export type UserTier = 'guest' | 'free' | 'paid'

interface Props {
  tier: UserTier
  requiredTier: 'free' | 'paid'
  onUpgrade?: () => void
  children: ReactNode
}

export default function AuthGate({ tier, requiredTier, onUpgrade, children }: Props) {
  if (tier === 'paid') return <>{children}</>
  if (requiredTier === 'free' && tier !== 'guest') return <>{children}</>

  const msg =
    tier === 'guest'
      ? '使用邀请码注册后继续'
      : '开通完整功能后查看完整分析'

  return (
    <div className="sqh-auth-gate">
      <p>{msg}</p>
      {onUpgrade && (
        <button onClick={onUpgrade}>
          {tier === 'guest' ? '注册 / 登录' : '开通完整功能'}
        </button>
      )}
    </div>
  )
}
