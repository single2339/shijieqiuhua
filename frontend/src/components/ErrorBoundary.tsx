import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', gap: 16,
          background: 'var(--bg-deep)', color: 'var(--text-primary)',
          fontFamily: 'var(--font-ui)',
        }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: 'var(--danger)',
            fontFamily: 'var(--font-mono)',
          }}>
            渲染错误
          </div>
          <div style={{
            fontSize: 12, color: 'var(--text-secondary)', maxWidth: 480, textAlign: 'center',
            lineHeight: 1.6, padding: '0 20px',
          }}>
            {this.state.error?.message || '未知错误'}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              background: 'var(--accent)', border: 'none', color: 'var(--bg-deep)',
              padding: '8px 20px', borderRadius: 'var(--radius-sm)',
              cursor: 'pointer', fontSize: 12, fontWeight: 600,
              fontFamily: 'var(--font-mono)',
            }}
          >
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
