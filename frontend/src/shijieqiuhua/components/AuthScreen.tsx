import { useState } from 'react'
import { ArrowLeft, ArrowRight, Gauge, ShieldCheck, Stack } from '@phosphor-icons/react'
import { motion } from 'framer-motion'

export interface AuthCredentials {
  username: string
  password: string
  email: string
  invite: string
}

interface AuthScreenProps {
  mode: 'login' | 'register'
  onModeChange: (mode: 'login' | 'register') => void
  onSubmit: (creds: AuthCredentials) => Promise<void>
  onBack: () => void
}

const ASIDE_FEATURES = [
  { ic: <Stack size={17} weight="duotone" />, t: '实时情报循环', d: '信源逐条点亮，研判过程全透明。' },
  { ic: <ShieldCheck size={17} weight="duotone" />, t: '诚实的不确定性', d: '缺数据时如实说「信息不足」。' },
  { ic: <Gauge size={17} weight="duotone" />, t: '可信度分级', d: '每个结论都带可靠性评级。' },
]

export default function AuthScreen({ mode, onModeChange, onSubmit, onBack }: AuthScreenProps) {
  const [name, setName] = useState('')
  const [pass, setPass] = useState('')
  const [email, setEmail] = useState('')
  const [invite, setInvite] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit() {
    if (!name || !pass) { setErr('请填写用户名和密码'); return }
    if (mode === 'register' && !invite) { setErr('注册需要邀请码'); return }
    setErr(''); setLoading(true)
    try {
      await onSubmit({ username: name, password: pass, email, invite })
    } catch (e) {
      setErr(e instanceof Error ? e.message : '认证失败')
    } finally {
      setLoading(false)
    }
  }

  function switchMode(m: 'login' | 'register') { onModeChange(m); setErr('') }

  return (
    <div className="sqh-auth-screen">
      <aside className="sqh-auth-aside">
        <div className="sqh-brand sqh-auth-brand" onClick={onBack}>
          <div className="sqh-mark">世</div>
          <div><h1>世界球花</h1><p>足球情报研判</p></div>
        </div>
        <div>
          <div className="sqh-auth-quote">每一条结论，<br />都看得见证据来源。</div>
          <div className="sqh-auth-feat">
            {ASIDE_FEATURES.map(f => (
              <div className="sqh-auth-feat-item" key={f.t}>
                <span className="sqh-auth-feat-ic">{f.ic}</span>
                <div><b>{f.t}</b><span>{f.d}</span></div>
              </div>
            ))}
          </div>
        </div>
        <div className="sqh-auth-aside-foot">不构成投注建议 · 理性看待研判结论</div>
      </aside>

      <main className="sqh-auth-main">
        <motion.div
          className="sqh-auth-form"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.2, 0.7, 0.3, 1] }}
        >
          <button className="btn btn-quiet btn-sm sqh-auth-back" onClick={onBack}>
            <ArrowLeft size={15} weight="bold" /> 返回首页
          </button>
          <h2 className="sqh-auth-title">{mode === 'login' ? '欢迎回来' : '创建账号'}</h2>
          <p className="sqh-auth-lead">
            {mode === 'login' ? '登录后继续你的情报研判。' : '注册即享每日 1 次完整研判。'}
          </p>

          <div className="sqh-auth-tabs">
            <button className={`sqh-auth-tab${mode === 'login' ? ' sqh-auth-tab--on' : ''}`}
              onClick={() => switchMode('login')}>登录</button>
            <button className={`sqh-auth-tab${mode === 'register' ? ' sqh-auth-tab--on' : ''}`}
              onClick={() => switchMode('register')}>注册</button>
          </div>

          <div className="sqh-auth-fields">
            <div className="field">
              <label>用户名</label>
              <input className="input" value={name} placeholder="你的用户名"
                onChange={e => setName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submit() }} />
            </div>
            <div className="field">
              <label>密码</label>
              <input className="input" type="password" value={pass} placeholder="••••••••"
                onChange={e => setPass(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submit() }} />
            </div>
            {mode === 'register' && (
              <>
                <div className="field">
                  <label>邮箱（选填）</label>
                  <input className="input" value={email} placeholder="name@example.com"
                    onChange={e => setEmail(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') submit() }} />
                </div>
                <div className="field">
                  <label>邀请码</label>
                  <input className="input" value={invite} placeholder="输入邀请码"
                    onChange={e => setInvite(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') submit() }} />
                </div>
              </>
            )}
            {err && <div className="sqh-auth-err">{err}</div>}
            <button className="btn btn-primary btn-lg btn-block" disabled={loading} onClick={submit}>
              {loading ? '处理中…' : <>{mode === 'login' ? '登录' : '注册并进入'} <ArrowRight size={16} weight="bold" /></>}
            </button>
          </div>

          <p className="sqh-auth-switch">
            {mode === 'login' ? '还没有账号？' : '已有账号？'}
            <a onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? '用邀请码注册' : '去登录'}
            </a>
          </p>
        </motion.div>
      </main>
    </div>
  )
}
