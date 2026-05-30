import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { X, Users, Ticket, ChartBar, CaretLeft, Trash, CheckCircle, XCircle, Plus } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import {
  fetchAdminUsers,
  updateAdminUser,
  fetchAdminInviteCodes,
  createAdminInviteCodes,
  fetchAdminStats,
} from '../api'
import type { AdminUserDetail, InviteCodeInfo, AdminStats } from '../types'

type Tab = 'users' | 'codes' | 'stats'

interface Props {
  onClose?: () => void
}

const tabDefs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'users', label: '用户管理', icon: <Users size={14} weight="duotone" /> },
  { key: 'codes', label: '邀请码', icon: <Ticket size={14} weight="duotone" /> },
  { key: 'stats', label: '统计', icon: <ChartBar size={14} weight="duotone" /> },
]

const panelStyle: React.CSSProperties = {
  background: 'var(--glass-bg)',
  backdropFilter: 'blur(24px)',
  border: '1px solid var(--glass-border)',
  borderRadius: 'var(--radius-lg)',
  boxShadow: 'var(--shadow-diffuse)',
}

const thStyle: React.CSSProperties = {
  textAlign: 'left', padding: '8px 12px', fontSize: 10, fontWeight: 600,
  color: 'var(--text-tertiary)', borderBottom: '1px solid var(--glass-border)',
  fontFamily: 'var(--font-mono)', textTransform: 'uppercase' as const, letterSpacing: 1,
}

const tdStyle: React.CSSProperties = {
  padding: '10px 12px', fontSize: 12, color: 'var(--text-primary)',
  borderBottom: '1px solid var(--border-subtle)',
}

function UsersTab() {
  const [users, setUsers] = useState<AdminUserDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setUsers(await fetchAdminUsers())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const toggleActive = async (userId: number, current: boolean) => {
    try {
      await updateAdminUser(userId, { is_active: !current })
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: !current } : u))
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ width: 200, height: 12, borderRadius: 99, background: 'var(--bg-elevated)', margin: '0 auto', animation: 'shimmer 2s linear infinite', backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(0,0,0,0.04) 50%, var(--bg-elevated) 75%)', backgroundSize: '200% 100%' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <p style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 12 }}>{error}</p>
        <button onClick={load} style={{ background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.25)', color: 'var(--danger)', padding: '4px 12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 11, fontFamily: 'var(--font-mono)' }}>重试</button>
      </div>
    )
  }

  if (users.length === 0) {
    return (
      <div style={{ padding: 60, textAlign: 'center' }}>
        <p style={{ fontSize: 13, color: 'var(--text-dim)' }}>暂无用户</p>
      </div>
    )
  }

  return (
    <div style={{ overflow: 'auto', maxHeight: 'calc(100dvh - 220px)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={thStyle}>ID</th>
            <th style={thStyle}>用户名</th>
            <th style={thStyle}>邮箱</th>
            <th style={thStyle}>角色</th>
            <th style={thStyle}>状态</th>
            <th style={thStyle}>操作数</th>
            <th style={thStyle}>注册时间</th>
            <th style={thStyle}>操作</th>
          </tr>
        </thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id}>
              <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-tertiary)' }}>{u.id}</td>
              <td style={tdStyle}>{u.username}</td>
              <td style={{ ...tdStyle, fontSize: 11, color: 'var(--text-secondary)' }}>{u.email}</td>
              <td style={tdStyle}>
                <span style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)',
                  padding: '2px 6px', borderRadius: 3,
                  background: u.role === 'admin' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.04)',
                  color: u.role === 'admin' ? 'var(--accent)' : 'var(--text-secondary)',
                }}>
                  {u.role === 'admin' ? '管理员' : '用户'}
                </span>
              </td>
              <td style={tdStyle}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10,
                  color: u.is_active ? 'var(--success)' : 'var(--danger)',
                }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: u.is_active ? 'var(--success)' : 'var(--danger)' }} />
                  {u.is_active ? '正常' : '已禁用'}
                </span>
              </td>
              <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 11 }}>{u.action_count}</td>
              <td style={{ ...tdStyle, fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {u.created_at?.slice(0, 10)}
              </td>
              <td style={tdStyle}>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => toggleActive(u.id, u.is_active)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    background: u.is_active ? 'rgba(220,38,38,0.06)' : 'rgba(16,185,129,0.06)',
                    border: `1px solid ${u.is_active ? 'rgba(220,38,38,0.15)' : 'rgba(16,185,129,0.15)'}`,
                    borderRadius: 'var(--radius-sm)', padding: '3px 8px',
                    color: u.is_active ? 'var(--danger)' : 'var(--success)',
                    cursor: 'pointer', fontSize: 10, fontFamily: 'var(--font-mono)',
                  }}
                >
                  {u.is_active ? <XCircle size={10} weight="bold" /> : <CheckCircle size={10} weight="bold" />}
                  {u.is_active ? '禁用' : '启用'}
                </motion.button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CodesTab() {
  const [codes, setCodes] = useState<InviteCodeInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [count, setCount] = useState(5)
  const [maxUses, setMaxUses] = useState(10)
  const [generating, setGenerating] = useState(false)

  const load = useCallback(async () => {
    try {
      setCodes(await fetchAdminInviteCodes())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const generate = async () => {
    setGenerating(true)
    setError('')
    try {
      await createAdminInviteCodes(count, maxUses)
      setCodes(await fetchAdminInviteCodes())
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'end', gap: 12, padding: '12px 0 20px',
        borderBottom: '1px solid var(--glass-border)', marginBottom: 20,
      }}>
        <div>
          <label style={{ display: 'block', fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>数量</label>
          <input type="number" value={count} onChange={e => setCount(Math.max(1, Math.min(50, Number(e.target.value))))}
            style={{
              width: 60, padding: '6px 8px', fontSize: 12,
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--glass-border)',
              background: 'var(--bg-surface)', color: 'var(--text-primary)',
              outline: 'none', fontFamily: 'var(--font-mono)',
            }} />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>可用次数</label>
          <input type="number" value={maxUses} onChange={e => setMaxUses(Math.max(1, Number(e.target.value)))}
            style={{
              width: 60, padding: '6px 8px', fontSize: 12,
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--glass-border)',
              background: 'var(--bg-surface)', color: 'var(--text-primary)',
              outline: 'none', fontFamily: 'var(--font-mono)',
            }} />
        </div>
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={generate}
          disabled={generating}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            background: generating ? 'var(--accent-dim)' : 'var(--accent)',
            border: 'none', borderRadius: 'var(--radius-sm)',
            color: '#fff', cursor: generating ? 'not-allowed' : 'pointer',
            padding: '6px 14px', fontSize: 11, fontFamily: 'var(--font-mono)',
          }}
        >
          <Plus size={10} weight="bold" />
          {generating ? '生成中...' : '生成'}
        </motion.button>
      </div>

      {error && <p style={{ fontSize: 11, color: 'var(--danger)', marginBottom: 12 }}>{error}</p>}

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <div style={{ width: 200, height: 12, borderRadius: 99, background: 'var(--bg-elevated)', margin: '0 auto', animation: 'shimmer 2s linear infinite', backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(0,0,0,0.04) 50%, var(--bg-elevated) 75%)', backgroundSize: '200% 100%' }} />
        </div>
      ) : codes.length === 0 ? (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <p style={{ fontSize: 13, color: 'var(--text-dim)' }}>暂无邀请码，请生成</p>
        </div>
      ) : (
        <div style={{ overflow: 'auto', maxHeight: 'calc(100dvh - 360px)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={thStyle}>邀请码</th>
                <th style={thStyle}>创建者</th>
                <th style={thStyle}>使用</th>
                <th style={thStyle}>状态</th>
                <th style={thStyle}>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {codes.map(c => (
                <tr key={c.id}>
                  <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 13, letterSpacing: 1, color: 'var(--accent)' }}>{c.code}</td>
                  <td style={{ ...tdStyle, fontSize: 11, color: 'var(--text-secondary)' }}>{c.created_by || '-'}</td>
                  <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    {c.current_uses} / {c.max_uses}
                  </td>
                  <td style={tdStyle}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10,
                      color: c.is_active ? 'var(--success)' : 'var(--danger)',
                    }}>
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.is_active ? 'var(--success)' : 'var(--danger)' }} />
                      {c.is_active ? '有效' : '已禁用'}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                    {c.created_at?.slice(0, 10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function StatsTab() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchAdminStats()
      .then(s => { setStats(s); setLoading(false) })
      .catch(err => { setError(err instanceof Error ? err.message : '加载失败'); setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ width: 200, height: 12, borderRadius: 99, background: 'var(--bg-elevated)', margin: '0 auto', animation: 'shimmer 2s linear infinite', backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(0,0,0,0.04) 50%, var(--bg-elevated) 75%)', backgroundSize: '200% 100%' }} />
      </div>
    )
  }

  if (error) {
    return <p style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--danger)' }}>{error}</p>
  }

  if (!stats) return null

  const statCards = [
    { label: '总用户数', value: stats.total_users },
    { label: '7日活跃', value: stats.active_7d },
    { label: '30日活跃', value: stats.active_30d },
    { label: '今日登录', value: stats.daily_logins?.[0]?.count ?? 0 },
    { label: '今日操作', value: stats.daily_actions?.[0]?.count ?? 0 },
  ]

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12, marginBottom: 28 }}>
        {statCards.map(c => (
          <div key={c.label} style={{ ...panelStyle, padding: '16px 18px', borderRadius: 'var(--radius-md)' }}>
            <p style={{ fontSize: 10, color: 'var(--text-tertiary)', margin: '0 0 6px', fontFamily: 'var(--font-mono)' }}>{c.label}</p>
            <p style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', margin: 0, fontFamily: 'var(--font-mono)' }}>{c.value}</p>
          </div>
        ))}
      </div>

      {stats.top_users && stats.top_users.length > 0 && (
        <div>
          <h3 style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', margin: '0 0 12px', fontFamily: 'var(--font-mono)' }}>活跃用户</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={thStyle}>用户</th>
                <th style={thStyle}>操作数</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_users.map((u: { username: string; action_count: number }) => (
                <tr key={u.username}>
                  <td style={tdStyle}>{u.username}</td>
                  <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{u.action_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function AdminPanel({ onClose }: Props) {
  const navigate = useNavigate()
  const { isAdmin, loading: authLoading } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('users')

  const handleClose = () => {
    if (onClose) onClose()
    else navigate('/')
  }

  if (authLoading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '100dvh', background: 'var(--bg-deep)',
      }}>
        <div style={{ width: 60, height: 60, borderRadius: '50%', border: '2px solid var(--glass-border)', borderTopColor: 'var(--accent)', animation: 'spin 0.6s linear infinite' }} />
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: '100dvh', background: 'var(--bg-deep)', gap: 16,
      }}>
        <p style={{ fontSize: 14, color: 'var(--danger)' }}>无权访问管理后台</p>
        <button onClick={() => navigate('/')} style={{
          background: 'rgba(255,255,255,0.06)', border: '1px solid var(--glass-border)',
          color: 'var(--text-secondary)', padding: '8px 20px', borderRadius: 'var(--radius-md)',
          cursor: 'pointer', fontSize: 12, fontFamily: 'var(--font-mono)',
        }}>
          返回首页
        </button>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: 'fixed', inset: 0, zIndex: 'var(--z-overlay)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)',
        padding: 24,
      }}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        style={{
          ...panelStyle,
          width: '100%', maxWidth: 900, maxHeight: '90dvh',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--glass-border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleClose}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: 'transparent', border: 'none',
                color: 'var(--text-tertiary)', cursor: 'pointer',
                padding: 4, fontFamily: 'var(--font-mono)', fontSize: 10,
              }}
            >
              <CaretLeft size={14} weight="bold" />
              返回
            </motion.button>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>管理后台</h2>
          </div>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={handleClose}
            style={{
              background: 'transparent', border: 'none',
              color: 'var(--text-tertiary)', cursor: 'pointer',
              padding: 4, display: 'flex',
            }}
          >
            <X size={18} weight="bold" />
          </motion.button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex', gap: 0, padding: '0 20px',
          borderBottom: '1px solid var(--glass-border)',
        }}>
          {tabDefs.map(t => (
            <motion.button
              key={t.key}
              whileHover={{ color: 'var(--text-primary)' }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setActiveTab(t.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '10px 16px',
                background: 'transparent', border: 'none',
                borderBottom: activeTab === t.key ? '2px solid var(--accent)' : '2px solid transparent',
                color: activeTab === t.key ? 'var(--accent)' : 'var(--text-tertiary)',
                cursor: 'pointer', fontSize: 11, fontFamily: 'var(--font-mono)',
                marginBottom: -1,
                transition: 'color 0.15s',
              }}
            >
              {t.icon}
              {t.label}
            </motion.button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: 20, flex: 1, overflow: 'auto' }}>
          {activeTab === 'users' && <UsersTab />}
          {activeTab === 'codes' && <CodesTab />}
          {activeTab === 'stats' && <StatsTab />}
        </div>
      </motion.div>
    </motion.div>
  )
}
