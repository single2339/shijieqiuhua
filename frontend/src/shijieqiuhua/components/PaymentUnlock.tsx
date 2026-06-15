import { useState } from 'react'
import { redeemCode } from '../api'
import type { AuthUser } from '../api'

interface Props { user: AuthUser; onRedeemed: (u: AuthUser) => void }

export default function PaymentUnlock({ user, onRedeemed }: Props) {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)

  async function submit() {
    const c = code.trim().toUpperCase()
    if (!c) return
    setLoading(true); setErr('')
    try {
      const result = await redeemCode(c)
      setDone(true)
      onRedeemed({
        ...user,
        entitlements: [
          ...user.entitlements,
          { type: result.type, granted_at: result.granted_at, expires_at: result.expires_at },
        ],
      })
    } catch (e) {
      setErr(e instanceof Error ? e.message : '兑换失败')
    } finally { setLoading(false) }
  }

  if (done) return <div style={{ padding: 12, borderRadius: 12, background: '#dcecd8', fontSize: 13, textAlign: 'center' }}>已开通完整功能</div>

  return (
    <div style={{ padding: 12, border: '1px dashed #c9a86a', borderRadius: 12, background: '#faf7e6' }}>
      <strong style={{ fontSize: 13 }}>开通完整功能</strong>
      <p style={{ fontSize: 11, color: '#6d725f', margin: '4px 0 8px' }}>输入付费码，解锁完整证据链和追问</p>
      <div className="sqh-input-row" style={{ marginTop: 0 }}>
        <input value={code} onChange={e => setCode(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submit() }}
          placeholder="付费码" style={{ flex: 1, padding: '6px 8px', border: '1px solid #e1d7c6', borderRadius: 8, fontSize: 12 }} />
        <button onClick={submit} disabled={loading}
          style={{ border: 0, borderRadius: 8, background: '#143c2d', color: '#f8f1df', padding: '6px 14px', fontWeight: 900, cursor: 'pointer', fontSize: 12 }}>
          {loading ? '兑换中' : '兑换'}
        </button>
      </div>
      {err && <div style={{ marginTop: 6, fontSize: 11, color: '#8a523f' }}>{err}</div>}
    </div>
  )
}
