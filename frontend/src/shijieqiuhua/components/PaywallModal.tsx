import { useState } from 'react'
import { ArrowRight, Check, Crown, Key, X } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { redeemCode } from '../api'
import type { AuthUser } from '../api'
import { PLANS } from '../plans'

interface PaywallModalProps {
  user: AuthUser | null
  onClose: () => void
  onPaid: (user: AuthUser) => void
}

export default function PaywallModal({ user, onClose, onPaid }: PaywallModalProps) {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function submit() {
    const c = code.trim().toUpperCase()
    if (!c) return
    if (!user) { setErr('请先登录'); return }
    setLoading(true); setErr('')
    try {
      const result = await redeemCode(c)
      onPaid({
        ...user,
        entitlements: [
          ...user.entitlements,
          { type: result.type, granted_at: result.granted_at, expires_at: result.expires_at },
        ],
      })
    } catch (e) {
      setErr(e instanceof Error ? e.message : '兑换失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="sqh-modal" onClick={onClose}>
      <motion.div
        className="sqh-modal-box"
        onClick={e => e.stopPropagation()}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: .22, ease: [.2, .7, .3, 1] }}
      >
        <div className="sqh-modal-hd">
          <div className="sqh-section-title">
            <Crown size={16} weight="duotone" />
            <span>解锁完整研判</span>
          </div>
          <button className="sqh-modal-x" onClick={onClose}><X size={16} weight="bold" /></button>
        </div>

        <div className="sqh-modal-bd">
          {/* plan cards */}
          <div className="sqh-plan-grid">
            {PLANS.map(p => (
              <div className={`sqh-plan${p.featured ? ' sqh-plan--featured' : ''}`} key={p.id}>
                {p.featured && <span className="sqh-plan-tag">最受欢迎</span>}
                <h3>{p.name}</h3>
                <div className="sqh-plan-price">
                  <span>¥</span><b>{p.price}</b><span>{p.unit}</span>
                </div>
                <ul className="sqh-plan-features">
                  {p.items.map(it => (
                    <li key={it}><Check size={14} weight="bold" />{it}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <hr className="hr" />

          {/* code redemption */}
          <div className="sqh-redeem">
            <div className="sqh-redeem-field">
              <label><Key size={13} weight="bold" /> 有兑换码？</label>
              <input
                className="input"
                placeholder="输入兑换码，立即升级"
                value={code}
                onChange={e => setCode(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submit() }}
              />
            </div>
            <button className="btn btn-gold" disabled={loading || !code} onClick={submit}>
              {loading ? '兑换中…' : <>兑换 <ArrowRight size={14} weight="bold" /></>}
            </button>
          </div>
          {err && <div className="sqh-auth-err" style={{ marginTop: 10 }}>{err}</div>}

          <p className="sqh-paywall-footnote">
            支付仅解锁分析能力，不构成任何投注建议。兑换后权益默认 30 天。
          </p>
        </div>
      </motion.div>
    </div>
  )
}
