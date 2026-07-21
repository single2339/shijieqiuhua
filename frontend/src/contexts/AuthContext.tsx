import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from 'react'
import type { UserInfo } from '../types'
import { clearUserScopedStorage } from '../utils/userStorage'
import { isAbortError } from '../utils/request'

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
  const authRequestGenerationRef = useRef(0)
  const authControllerRef = useRef<AbortController | null>(null)

  const beginAuthRequest = useCallback(() => {
    authRequestGenerationRef.current += 1
    authControllerRef.current?.abort()
    const controller = new AbortController()
    authControllerRef.current = controller
    return { generation: authRequestGenerationRef.current, controller }
  }, [])

  const verifySession = useCallback(async () => {
    const { generation, controller } = beginAuthRequest()
    try {
      const res = await fetch('/api/auth/me', { signal: controller.signal })
      if (controller.signal.aborted || generation !== authRequestGenerationRef.current) return
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
    } catch (error) {
      if (isAbortError(error) || generation !== authRequestGenerationRef.current) return
      setState(s => ({ ...s, loading: false }))
    } finally {
      if (authControllerRef.current === controller) authControllerRef.current = null
    }
  }, [beginAuthRequest])

  useEffect(() => {
    void verifySession()
    return () => {
      authRequestGenerationRef.current += 1
      authControllerRef.current?.abort()
    }
  }, [verifySession])

  const login = useCallback(async (username: string, password: string) => {
    const { generation, controller } = beginAuthRequest()
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      signal: controller.signal,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error((data as { detail?: string }).detail || '登录失败')
    }
    const data = await res.json()
    if (controller.signal.aborted || generation !== authRequestGenerationRef.current) return
    setState({
      user: data.user,
      isAuthenticated: true,
      isAdmin: data.user.role === 'admin',
      loading: false,
    })
    if (authControllerRef.current === controller) authControllerRef.current = null
  }, [beginAuthRequest])

  const register = useCallback(async (username: string, email: string, password: string, inviteCode: string) => {
    const { generation, controller } = beginAuthRequest()
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password, invite_code: inviteCode }),
      signal: controller.signal,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error((data as { detail?: string }).detail || '注册失败')
    }
    const data = await res.json()
    if (controller.signal.aborted || generation !== authRequestGenerationRef.current) return
    setState({
      user: data.user,
      isAuthenticated: true,
      isAdmin: data.user.role === 'admin',
      loading: false,
    })
    if (authControllerRef.current === controller) authControllerRef.current = null
  }, [beginAuthRequest])

  const logout = useCallback(() => {
    authRequestGenerationRef.current += 1
    authControllerRef.current?.abort()
    authControllerRef.current = null
    clearUserScopedStorage(state.user?.id)
    fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } }).catch(() => {})
    setState({
      user: null,
      isAuthenticated: false,
      isAdmin: false,
      loading: false,
    })
  }, [state.user?.id])

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
