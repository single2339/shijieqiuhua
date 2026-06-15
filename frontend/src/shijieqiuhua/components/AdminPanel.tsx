import { useState } from 'react'
import type { AuthUser } from '../api'

interface Props { user: AuthUser }

export default function AdminPanel({ user }: Props) {
  if (user.role !== 'admin') return null
  return (
    <div style={{ marginTop: 8 }}>
      <div className="sqh-section-title"><span>管理面板</span></div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        <CodeGen label="生成邀请码" endpoint="/api/admin/invite-codes" />
        <CodeList label="邀请码列表" endpoint="/api/admin/invite-codes" fields={['code', 'current_uses', 'max_uses', 'is_active', 'expires_at']} />
        <CodeGen label="生成付费码" endpoint="/api/admin/payment-codes" />
        <CodeList label="付费码列表" endpoint="/api/admin/payment-codes" fields={['code', 'status', 'expires_at']} />
        <UserList />
      </div>
    </div>
  )
}

function CodeGen({ label, endpoint }: { label: string; endpoint: string }) {
  const [count, setCount] = useState(10)
  const [msg, setMsg] = useState('')
  const [codes, setCodes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  async function go() {
    setLoading(true); setMsg(''); setCodes([])
    try {
      const res = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ count, max_uses: 1, expires_days: 30 }) })
      if (res.status === 401) { setMsg('登录已过期，请重新登录'); return }
      const d = await res.json()
      if (res.ok) { setMsg(`已生成 ${count} 个`); setCodes(d.codes || []) }
      else setMsg(`失败: ${d.detail}`)
    } catch { setMsg('请求失败') } finally { setLoading(false) }
  }
  return (
    <div style={{ marginTop: 6, padding: 6, borderRadius: 8, background: '#f4edd5' }}>
      <strong style={{ fontSize: 12 }}>{label}</strong>
      <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
        <input type="number" value={count} onChange={e => setCount(Number(e.target.value))} min={1} max={100} style={{ width: 48, padding: '2px 4px', border: '1px solid #e1d7c6', borderRadius: 6, fontSize: 11 }} />
        <button onClick={go} disabled={loading} style={{ border: 0, borderRadius: 6, background: '#143c2d', color: '#f8f1df', padding: '2px 8px', fontWeight: 700, fontSize: 11, cursor: 'pointer' }}>{loading ? '…' : '生成'}</button>
        {codes.length > 0 && (
          <button onClick={() => navigator.clipboard.writeText(codes.join('\n'))} style={{ border: '1px solid #e1d7c6', borderRadius: 6, background: 'transparent', color: '#143c2d', padding: '2px 8px', fontSize: 11, cursor: 'pointer' }}>复制全部</button>
        )}
      </div>
      {msg && <div style={{ marginTop: 2, fontSize: 11, color: '#6d725f' }}>{msg}</div>}
      {codes.length > 0 && (
        <textarea readOnly value={codes.join('\n')} style={{ marginTop: 4, width: '100%', height: Math.min(120, 20 + codes.length * 16), fontSize: 11, fontFamily: 'monospace', padding: 4, border: '1px solid #e1d7c6', borderRadius: 6, resize: 'vertical', boxSizing: 'border-box' }} />
      )}
    </div>
  )
}

type CodeRecord = Record<string, string | number | boolean | null>

function CodeList({ label, endpoint, fields }: { label: string; endpoint: string; fields: string[] }) {
  const [rows, setRows] = useState<CodeRecord[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  async function toggle() {
    if (open) { setOpen(false); return }
    setLoading(true); setErr('')
    try {
      const r = await fetch(endpoint)
      if (r.status === 401) { setErr('登录已过期，请重新登录'); return }
      setRows(await r.json())
      setOpen(true)
    } catch { setErr('请求失败') } finally { setLoading(false) }
  }
  return (
    <div style={{ marginTop: 6, padding: 6, borderRadius: 8, background: '#edf3e8' }}>
      <strong style={{ fontSize: 12, cursor: 'pointer' }} onClick={toggle}>{loading ? '加载中…' : open ? `收起${label}` : label}</strong>
      {err && <div style={{ marginTop: 2, fontSize: 11, color: '#8a523f' }}>{err}</div>}
      {open && (
        <div style={{ marginTop: 4, maxHeight: 200, overflow: 'auto' }}>
          {rows.length === 0 && <div style={{ fontSize: 11, color: '#6d725f' }}>暂无数据</div>}
          {rows.map((row, i) => (
            <div key={i} style={{ fontSize: 11, padding: '1px 0', borderBottom: '1px solid #dce6d8', display: 'flex', gap: 6, fontFamily: 'monospace' }}>
              {fields.map(f => <span key={f}>{String(row[f] ?? '')}</span>)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function UserList() {
  const [users, setUsers] = useState<{ id: number; username: string; role: string; is_active: boolean }[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  async function toggle() {
    if (open) { setOpen(false); return }
    setLoading(true); setErr('')
    try {
      const r = await fetch('/api/admin/users?page_size=50')
      if (r.status === 401) { setErr('登录已过期，请重新登录'); return }
      setUsers(((await r.json()).users || []))
      setOpen(true)
    } catch { setErr('请求失败') } finally { setLoading(false) }
  }
  return (
    <div style={{ marginTop: 6, padding: 6, borderRadius: 8, background: '#edf3e8' }}>
      <strong style={{ fontSize: 12, cursor: 'pointer' }} onClick={toggle}>{loading ? '加载中…' : open ? '收起用户' : '用户列表'}</strong>
      {err && <div style={{ marginTop: 2, fontSize: 11, color: '#8a523f' }}>{err}</div>}
      {open && (
        <div style={{ marginTop: 4, maxHeight: 200, overflow: 'auto' }}>
          {users.map(u => (
            <div key={u.id} style={{ fontSize: 11, padding: '1px 0', borderBottom: '1px solid #dce6d8', display: 'flex', justifyContent: 'space-between' }}>
              <span>{u.username} <span style={{ color: '#6d725f' }}>{u.role}</span></span>
              <span style={{ color: u.is_active ? '#143c2d' : '#8a523f' }}>{u.is_active ? '正常' : '禁用'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
