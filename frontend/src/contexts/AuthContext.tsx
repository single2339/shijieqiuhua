import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react'
import type { UserInfo } from '../types'

interface AuthState {
  user: UserInfo | null
  isAuthenticated: boolean
  isAdmin: boolean
  loading: boolean
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string, inviteCode: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isAdmin: false,
    loading: true,
  })

  const verifySession = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/me')
      if (res.ok) {
        const user = await res.json()
        setState({
          user,
          isAuthenticated: true,
          isAdmin: user.role === 'admin',
          loading: false,
        })
      } else {
        setState({ user: null, isAuthenticated: false, isAdmin: false, loading: false })
      }
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }, [])

  useEffect(() => {
    verifySession()
  }, [verifySession])

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error((data as { detail?: string }).detail || '登录失败')
    }
    const data = await res.json()
    setState({
      user: data.user,
      isAuthenticated: true,
      isAdmin: data.user.role === 'admin',
      loading: false,
    })
  }, [])

  const register = useCallback(async (username: string, email: string, password: string, inviteCode: string) => {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password, invite_code: inviteCode }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error((data as { detail?: string }).detail || '注册失败')
    }
    const data = await res.json()
    setState({
      user: data.user,
      isAuthenticated: true,
      isAdmin: data.user.role === 'admin',
      loading: false,
    })
  }, [])

  const logout = useCallback(() => {
    fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } }).catch(() => {})
    setState({
      user: null,
      isAuthenticated: false,
      isAdmin: false,
      loading: false,
    })
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
