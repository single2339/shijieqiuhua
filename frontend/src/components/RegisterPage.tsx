import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !email.trim() || !password || !inviteCode.trim()) {
      setError('请填写所有字段')
      return
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    if (password.length < 6) {
      setError('密码长度至少 6 位')
      return
    }
    setError('')
    setLoading(true)
    try {
      await register(username.trim(), email.trim(), password, inviteCode.trim())
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册失败')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    width: '100%', padding: '10px 14px', fontSize: 14,
    borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)',
    background: 'var(--bg-surface)', color: 'var(--text-primary)',
    outline: 'none', boxSizing: 'border-box' as const,
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100dvh', background: 'var(--bg-deep)', padding: '24px',
    }}>
      <div className="command-panel" style={{
        width: '100%', maxWidth: 400, padding: '40px 32px',
      }}>
        <h1 style={{
          fontSize: 24, fontWeight: 700, color: 'var(--accent)',
          margin: '0 0 8px', letterSpacing: '-0.02em',
        }}>
          OSINT Network
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: '0 0 32px' }}>
          使用邀请码注册新账号
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>用户名</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)} autoFocus style={inputStyle} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>邮箱</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} style={inputStyle} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>密码</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} style={inputStyle} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>确认密码</label>
            <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} style={inputStyle} />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>邀请码</label>
            <input type="text" value={inviteCode} onChange={e => setInviteCode(e.target.value)} style={inputStyle} />
          </div>

          {error && (
            <p style={{ fontSize: 12, color: 'var(--danger)', margin: '0 0 16px' }}>{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '12px', fontSize: 14, fontWeight: 600,
              borderRadius: 'var(--radius-md)', border: 'none',
              background: loading ? 'var(--accent-dim)' : 'var(--accent)',
              color: 'var(--bg-deep)', cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {loading ? '注册中...' : '注册'}
          </button>
        </form>

        <p style={{ fontSize: 12, color: 'var(--text-dim)', textAlign: 'center', marginTop: 24 }}>
          已有账号？<Link to="/login" style={{ color: 'var(--accent)', textDecoration: 'none' }}>登录</Link>
        </p>
      </div>
    </div>
  )
}
