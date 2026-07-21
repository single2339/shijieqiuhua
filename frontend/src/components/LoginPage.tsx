import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('请填写用户名和密码')
      return
    }
    setError('')
    setLoading(true)
    try {
      await login(username.trim(), password)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
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
          登录以使用情报分析功能
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
              style={{
                width: '100%', padding: '10px 14px', fontSize: 14,
                borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)',
                background: 'var(--bg-surface)', color: 'var(--text-primary)',
                outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{
                width: '100%', padding: '10px 14px', fontSize: 14,
                borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)',
                background: 'var(--bg-surface)', color: 'var(--text-primary)',
                outline: 'none', boxSizing: 'border-box',
              }}
            />
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
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        <p style={{ fontSize: 12, color: 'var(--text-dim)', textAlign: 'center', marginTop: 24 }}>
          没有账号？<Link to="/register" style={{ color: 'var(--accent)', textDecoration: 'none' }}>使用邀请码注册</Link>
        </p>
      </div>
    </div>
  )
}
