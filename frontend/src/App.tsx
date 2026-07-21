import { lazy, Suspense, useEffect, useState, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { MagnifyingGlass, FileText, ChartBar, ArrowsClockwise, Database, Rows, MapPin, Brain, List, CaretLeft, CaretRight, User, SignOut, Gear, LockKey } from '@phosphor-icons/react'
import type { BriefWorkspace, BriefWorkspaceMaterial, IntelItem, IntelLayer, DashboardData } from './types'
import { LAYER_META } from './types'
import { changePassword } from './api'
import { useAuth } from './contexts/AuthContext'
import { useIsMobile } from './hooks/useMediaQuery'
import { useDashboardData } from './hooks/useDashboardData'
import { useAnalysisContext } from './hooks/useAnalysisContext'
import { confidenceColor, itemConfidenceLevel, itemToBriefMaterial, warningColor } from './utils/intelDisplay'
import { BRIEF_WORKSPACE_STORAGE_KEY, getUserStorageKey } from './utils/userStorage'
import LayerPanel from './components/LayerPanel'
import StatusDot from './components/StatusDot'

const loadMapView = () => import('./components/MapView')
const MapView = lazy(loadMapView)
const IntelCard = lazy(() => import('./components/IntelCard'))
const MessageFeed = lazy(() => import('./components/MessageFeed'))
const AskPanel = lazy(() => import('./components/AskPanel'))
const StatsPanel = lazy(() => import('./components/StatsPanel'))
const ReportPanel = lazy(() => import('./components/ReportPanel'))
const SourcePanel = lazy(() => import('./components/SourcePanel'))
const IntelAnalysisPanel = lazy(() => import('./components/IntelAnalysisPanel'))
const SuperAnalysisPanel = lazy(() => import('./components/SuperAnalysisPanel'))
const MobileMenu = lazy(() => import('./components/MobileMenu'))
const LoginPage = lazy(() => import('./components/LoginPage'))
const RegisterPage = lazy(() => import('./components/RegisterPage'))
const AdminPanel = lazy(() => import('./components/AdminPanel'))

const ALL_LAYERS: IntelLayer[] = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber']

type AnalysisFocus = {
  item: IntelItem
  eventId?: string
}

const SHIMMER_STYLE: React.CSSProperties = {
  backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(236,230,218,0.04) 50%, var(--bg-elevated) 75%)',
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.5s ease-in-out infinite',
}

const SKELETON_ITEM_STYLE: React.CSSProperties = {
  height: 40, borderRadius: 'var(--radius-md)',
  background: 'var(--bg-elevated)',
  backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(236,230,218,0.035) 50%, var(--bg-elevated) 75%)',
  backgroundSize: '200% 100%',
}

function LiveClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)', letterSpacing: 1 }}>
      {time.toLocaleTimeString('zh-CN', { hour12: false })}
    </span>
  )
}

interface ActionBtnProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
  accent?: boolean
}

function ActionBtn({ icon, label, onClick, accent }: ActionBtnProps) {
  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className="interactive-btn"
      style={{
        display: 'flex', alignItems: 'center', gap: 4,
        background: 'transparent', border: 'none',
        color: accent ? 'var(--accent)' : 'var(--text-tertiary)',
        cursor: 'pointer', padding: '2px 6px',
        fontSize: 9, fontFamily: 'var(--font-mono)',
        whiteSpace: 'nowrap',
      }}
    >
      {icon}
      {label}
    </motion.button>
  )
}

function InlineModuleFallback({ label = '加载中' }: { label?: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: 80, color: 'var(--text-tertiary)',
      fontFamily: 'var(--font-mono)', fontSize: 10,
    }}>
      {label}
    </div>
  )
}

function RouteFallback() {
  return (
    <div className="workstation-shell" style={{
      minHeight: '100dvh', background: 'var(--bg-deep)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div className="command-panel" style={{
        width: 220, padding: 18, textAlign: 'center',
        color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10,
      }}>
        系统模块加载中
      </div>
    </div>
  )
}

function MapModuleFallback() {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      background:
        'radial-gradient(circle at 50% 38%, rgba(200,164,93,0.08), transparent 32%), var(--bg-deep)',
    }} />
  )
}

function emptyBriefWorkspace(): BriefWorkspace {
  return { materials: [], updated_at: new Date().toISOString() }
}

function loadBriefWorkspace(userId: number | null): BriefWorkspace {
  const storageKey = getUserStorageKey(BRIEF_WORKSPACE_STORAGE_KEY, userId)
  if (!storageKey || typeof window === 'undefined') return emptyBriefWorkspace()

  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return emptyBriefWorkspace()
    const parsed = JSON.parse(raw) as Partial<BriefWorkspace>
    if (Array.isArray(parsed.materials)) {
      return {
        materials: parsed.materials,
        updated_at: typeof parsed.updated_at === 'string' ? parsed.updated_at : new Date().toISOString(),
      }
    }
  } catch {
    // Local draft corruption should not block the workstation.
  }
  return emptyBriefWorkspace()
}

function CommandSummary({
  data,
  activeLayerCount,
  selectedDate,
  lastUpdated,
}: {
  data: DashboardData | null
  activeLayerCount: number
  selectedDate: string
  lastUpdated: string
}) {
  const sourceCount = data?.sources.length ?? 0
  const populatedLayers = data?.layers.filter(l => l.count > 0).length ?? 0
  return (
    <motion.aside
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20, delay: 0.25 }}
      className="command-panel scanline"
      style={{
        position: 'absolute',
        left: 64,
        bottom: 52,
        width: 292,
        zIndex: 'var(--z-map-controls)',
        padding: '14px 16px',
        fontFamily: 'var(--font-ui)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 9, color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 800, letterSpacing: 1.2 }}>
            LIVE SITUATION BOARD
          </div>
          <div style={{ marginTop: 2, fontSize: 12, color: 'var(--text-primary)', fontWeight: 650 }}>
            全天情报态势
          </div>
        </div>
        <div style={{ position: 'relative', width: 9, height: 9, flexShrink: 0 }}>
          <span style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            background: 'var(--accent)', opacity: 0.9,
          }} />
          <span style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            background: 'var(--accent)', animation: 'status-breathe 2.4s ease-out infinite',
          }} />
        </div>
      </div>
      <div className="metric-line">
        <span style={{ color: 'var(--text-tertiary)', fontSize: 10 }}>情报总量</span>
        <span className="numeric" style={{ color: 'var(--text-primary)', fontSize: 20, fontWeight: 800 }}>
          {data?.total_items ?? '---'}
        </span>
      </div>
      <div className="metric-line">
        <span style={{ color: 'var(--text-tertiary)', fontSize: 10 }}>来源 / 图层</span>
        <span className="numeric" style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
          {sourceCount} SRC · {activeLayerCount}/{populatedLayers || activeLayerCount} LAYERS
        </span>
      </div>
      <div className="metric-line">
        <span style={{ color: 'var(--text-tertiary)', fontSize: 10 }}>日期 / 刷新</span>
        <span className="numeric" style={{ color: 'var(--accent)', fontSize: 11 }}>
          {selectedDate} · {lastUpdated}
        </span>
      </div>
    </motion.aside>
  )
}

function Dashboard() {
  const isMobile = useIsMobile()
  const { user, isAuthenticated, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [showChangePwd, setShowChangePwd] = useState(false)
  const [changePwdError, setChangePwdError] = useState('')
  const [changePwdLoading, setChangePwdLoading] = useState(false)
  const [activeLayers, setActiveLayers] = useState<Set<IntelLayer>>(new Set(ALL_LAYERS))
  const [selectedItem, setSelectedItem] = useState<IntelItem | null>(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10))
  const [activePanel, setActivePanel] = useState<string | null>(null)
  const [analysisFocus, setAnalysisFocus] = useState<AnalysisFocus | null>(null)
  const currentUserId = user?.id ?? null
  const [briefWorkspace, setBriefWorkspace] = useState<BriefWorkspace>(() => emptyBriefWorkspace())
  const [briefWorkspaceOwner, setBriefWorkspaceOwner] = useState<number | null>(null)
  const [showFeeds, setShowFeeds] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [mapReady, setMapReady] = useState(false)

  const {
    data, loading, error, lastUpdated, collecting,
    feedPage, feedItems, loadingMore, hasMore,
    loadData, loadMoreItems, triggerCollect,
  } = useDashboardData(startDate, endDate, selectedDate)

  const availableDates = data?.available_dates ?? []
  const currentDateIndex = availableDates.indexOf(selectedDate)
  const hasPrevDate = currentDateIndex < availableDates.length - 1
  const hasNextDate = currentDateIndex > 0

  const navigateDate = useCallback((direction: -1 | 1) => {
    if (currentDateIndex === -1) return
    const newIndex = currentDateIndex - direction
    if (newIndex >= 0 && newIndex < availableDates.length) {
      setSelectedDate(availableDates[newIndex])
    }
  }, [currentDateIndex, availableDates])

  const goToToday = useCallback(() => {
    setSelectedDate(new Date().toISOString().slice(0, 10))
  }, [])

  const toggleLayer = useCallback((layer: IntelLayer) => {
    setActiveLayers(prev => { const n = new Set(prev); n.has(layer) ? n.delete(layer) : n.add(layer); return n })
  }, [])

  const mapItems = useMemo(() => feedItems.filter(i => activeLayers.has(i.layer)), [feedItems, activeLayers])
  const feedFilteredItems = mapItems
  const activeLayerList = useMemo(() => Array.from(activeLayers), [activeLayers])
  const analysisFocusDate = selectedItem?.captured_at?.slice(0, 10) || analysisFocus?.item.captured_at?.slice(0, 10) || ''
  const analysisContext = useAnalysisContext(
    selectedDate,
    startDate,
    endDate,
    activeLayerList,
    showFeeds || selectedItem !== null || activePanel === 'analysis',
    analysisFocusDate,
  )

  useEffect(() => {
    if (!loading) void loadMapView().catch(() => undefined)
  }, [loading])

  useEffect(() => {
    if (loading || mapReady) return
    if ('requestIdleCallback' in window) {
      const idleId = window.requestIdleCallback(() => setMapReady(true), { timeout: 1_500 })
      return () => window.cancelIdleCallback(idleId)
    }
    const timeoutId = globalThis.setTimeout(() => setMapReady(true), 250)
    return () => globalThis.clearTimeout(timeoutId)
  }, [loading, mapReady])

  useEffect(() => {
    setBriefWorkspace(loadBriefWorkspace(currentUserId))
    setBriefWorkspaceOwner(currentUserId)
  }, [currentUserId])

  useEffect(() => {
    if (!data?.intel_items.length) return
    setSelectedItem(prev => {
      if (!prev) return prev
      return data.intel_items.find(item => item.id === prev.id) ?? prev
    })
  }, [data?.intel_items])

  useEffect(() => {
    if (briefWorkspaceOwner !== currentUserId) return
    const storageKey = getUserStorageKey(BRIEF_WORKSPACE_STORAGE_KEY, currentUserId)
    if (!storageKey) return
    window.localStorage.setItem(storageKey, JSON.stringify(briefWorkspace))
  }, [briefWorkspace, briefWorkspaceOwner, currentUserId])

  const addBriefMaterial = useCallback((material: BriefWorkspaceMaterial) => {
    setBriefWorkspace(prev => {
      const nextMaterial = {
        ...material,
        summary: material.summary || '',
        sources: material.sources ?? [],
      }
      const existingIndex = prev.materials.findIndex(item => item.type === nextMaterial.type && item.id === nextMaterial.id)
      const materials = existingIndex >= 0
        ? prev.materials.map((item, index) => index === existingIndex ? nextMaterial : item)
        : [nextMaterial, ...prev.materials]
      return { materials, updated_at: new Date().toISOString() }
    })
  }, [])

  const removeBriefMaterial = useCallback((type: BriefWorkspaceMaterial['type'], id: string) => {
    setBriefWorkspace(prev => ({
      materials: prev.materials.filter(item => item.type !== type || item.id !== id),
      updated_at: new Date().toISOString(),
    }))
  }, [])

  const clearBriefWorkspace = useCallback(() => {
    setBriefWorkspace({ materials: [], updated_at: new Date().toISOString() })
  }, [])

  const addItemToBrief = useCallback((item: IntelItem) => {
    addBriefMaterial(itemToBriefMaterial(item, '情报卡片'))
    setSelectedItem(null)
    if (!isAuthenticated) {
      navigate('/login')
      return
    }
    setActivePanel('report')
  }, [addBriefMaterial, isAuthenticated, navigate])

  const openPanel = (panel: string) => {
    setShowMenu(false)
    if ((panel === 'ask' || panel === 'report' || panel === 'super') && !isAuthenticated) {
      navigate('/login')
      return
    }
    if (panel === 'analysis') setAnalysisFocus(null)
    setActivePanel(panel)
  }

  const analyzeItem = useCallback((item: IntelItem) => {
    const context = analysisContext.itemContext[item.id]
    setAnalysisFocus({ item, eventId: context?.eventId })
    setSelectedItem(null)
    setShowFeeds(false)
    setActivePanel('analysis')
  }, [analysisContext.itemContext])

  return (
    <div className="workstation-shell" style={{ width: '100vw', minHeight: '100dvh', height: '100dvh', overflow: 'hidden', background: 'var(--bg-deep)', position: 'relative' }}>
      {/* Full-screen Map */}
      <div style={{ position: 'absolute', inset: 0 }}>
        {!loading && mapReady && (
          <Suspense fallback={<MapModuleFallback />}>
            <MapView items={mapItems} onSelect={setSelectedItem} />
          </Suspense>
        )}
        <div className="map-grid-overlay" />
      </div>

      {/* Top Bar — desktop: full actions; mobile: compact + hamburger */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        className="glass-panel"
        style={{
          position: 'absolute', top: isMobile ? 8 : 12,
          left: isMobile ? 8 : 64, right: isMobile ? 8 : 16,
          height: isMobile ? 42 : 44,
          borderRadius: 'var(--radius-md)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: isMobile ? '0 8px 0 10px' : '0 12px 0 16px',
          zIndex: 'var(--z-top-bar)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 6 : 14 }}>
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            style={{ fontSize: isMobile ? 12 : 11, color: 'var(--accent)', letterSpacing: isMobile ? 2 : 4, fontWeight: 800 }}
          >
            OSINT
          </motion.span>
          {!isMobile && (
            <>
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)', letterSpacing: 1, fontFamily: 'var(--font-ui)' }}>
                全球情报研判工作台
              </span>
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Database size={10} weight="duotone" color="var(--text-tertiary)" />
                情报 <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{data?.total_items ?? '---'}</span>
              </span>
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <MapPin size={10} weight="duotone" color="var(--text-tertiary)" />
                来源 <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{data?.sources.length ?? '---'}</span>
              </span>
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => navigateDate(-1)}
                disabled={!hasPrevDate}
                className="interactive-btn"
                style={{
                  background: 'transparent', border: 'none',
                  color: 'var(--text-tertiary)',
                  cursor: hasPrevDate ? 'pointer' : 'default',
                  padding: '2px 0', display: 'flex',
                  opacity: hasPrevDate ? 0.7 : 0.25,
                }}
              >
                <CaretLeft size={10} weight="bold" />
              </motion.button>
              <span style={{
                fontSize: 9, color: 'var(--accent)', fontFamily: 'var(--font-mono)',
                fontWeight: 600, minWidth: 72, textAlign: 'center' as const,
              }}>
                {selectedDate === new Date().toISOString().slice(0, 10)
                  ? '今天'
                  : selectedDate.slice(5).replace('-', '月') + '日'}
              </span>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => navigateDate(1)}
                disabled={!hasNextDate}
                className="interactive-btn"
                style={{
                  background: 'transparent', border: 'none',
                  color: 'var(--text-tertiary)',
                  cursor: hasNextDate ? 'pointer' : 'default',
                  padding: '2px 0', display: 'flex',
                  opacity: hasNextDate ? 0.7 : 0.25,
                }}
              >
                <CaretRight size={10} weight="bold" />
              </motion.button>
              {selectedDate !== new Date().toISOString().slice(0, 10) && (
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={goToToday}
                  className="interactive-btn"
                  style={{
                    background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.22)',
                    color: 'var(--accent)', cursor: 'pointer',
                    padding: '1px 6px', borderRadius: 3,
                    fontSize: 8, fontFamily: 'var(--font-mono)',
                  }}
                >
                  今天
                </motion.button>
              )}
            </>
          )}
          {isMobile && (
            <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-ui)' }}>
              {data?.total_items ?? '---'} 条情报
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 4 : 6, fontSize: 10 }}>
          {isMobile ? (
            <>
              {isAuthenticated ? (
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  onClick={() => navigate('/admin')}
                  className="interactive-btn mobile-touch-target"
                  style={{
                    background: 'transparent', border: 'none',
                    color: isAdmin ? 'var(--accent)' : 'var(--text-tertiary)',
                    cursor: 'pointer', padding: 4,
                    display: isAdmin ? 'flex' : 'none',
                  }}
                >
                  <Gear size={14} weight="bold" />
                </motion.button>
              ) : (
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  onClick={() => navigate('/login')}
                  className="interactive-btn mobile-touch-target"
                  style={{
                    background: 'transparent', border: 'none',
                    color: 'var(--accent)', cursor: 'pointer', padding: 4,
                  }}
                >
                  <User size={14} weight="bold" />
                </motion.button>
              )}
              <StatusDot loading={loading} error={!!error} />
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => loadData()}
                className="interactive-btn mobile-touch-target"
                style={{
                  background: 'transparent', border: 'none',
                  color: 'var(--text-tertiary)', cursor: 'pointer',
                  padding: 4,
                }}
              >
                <ArrowsClockwise size={14} weight="bold" />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setShowMenu(true)}
                className="interactive-btn mobile-touch-target"
                style={{
                  background: 'transparent', border: 'none',
                  color: 'var(--text-tertiary)', cursor: 'pointer',
                  padding: 4,
                }}
              >
                <List size={18} weight="bold" />
              </motion.button>
            </>
          ) : (
            <>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => openPanel('ask')}
                className="interactive-btn"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  background: 'rgba(236,230,218,0.04)', border: '1px solid var(--glass-border)',
                  borderRadius: 'var(--radius-sm)', padding: '2px 10px',
                  color: 'var(--text-tertiary)', fontSize: 9,
                  fontFamily: 'var(--font-mono)', cursor: 'pointer',
                }}
              >
                <MagnifyingGlass size={10} color="var(--accent)" weight="duotone" />
                情报查询
              </motion.button>
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              <StatusDot loading={loading} error={!!error} />
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => loadData()}
                title="刷新"
                className="interactive-btn"
                style={{
                  background: 'transparent', border: 'none',
                  color: 'var(--text-tertiary)', cursor: 'pointer',
                  padding: '2px 4px', display: 'flex',
                }}
              >
                <ArrowsClockwise size={12} weight="bold" />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={triggerCollect}
                disabled={collecting}
                className="interactive-btn"
                style={{
                  background: 'var(--accent-dim)',
                  border: collecting ? '1px solid transparent' : '1px solid rgba(200,164,93,0.22)',
                  borderRadius: 'var(--radius-sm)',
                  color: collecting ? 'var(--text-tertiary)' : 'var(--accent)',
                  cursor: collecting ? 'default' : 'pointer',
                  padding: '2px 8px', fontSize: 9,
                  fontFamily: 'var(--font-mono)', opacity: collecting ? 0.6 : 1,
                }}
              >
                {collecting ? '采集中...' : '+采集'}
              </motion.button>
              <ActionBtn icon={<ChartBar size={10} weight="duotone" />} label="看板" onClick={() => openPanel('stats')} />
              <ActionBtn icon={<FileText size={10} weight="duotone" />} label="简报" onClick={() => openPanel('report')} />
              <ActionBtn icon={<Brain size={10} weight="duotone" />} label="超级" onClick={() => openPanel('super')} accent />
              <ActionBtn icon={<ChartBar size={10} weight="duotone" />} label="分析" onClick={() => openPanel('analysis')} />
              <ActionBtn icon={<Rows size={10} weight="duotone" />} label="来源" onClick={() => setShowSources(!showSources)} />
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              {isAuthenticated && isAdmin && (
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/admin')}
                  className="interactive-btn"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 3,
                    background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.22)',
                    borderRadius: 'var(--radius-sm)', padding: '1px 6px',
                    color: 'var(--accent)', fontSize: 9,
                    fontFamily: 'var(--font-mono)', cursor: 'pointer',
                  }}
                >
                  <Gear size={9} weight="bold" />
                  管理
                </motion.button>
              )}
              {isAuthenticated ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <User size={10} weight="duotone" color="var(--text-tertiary)" />
                  <span style={{ fontSize: 9, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{user?.username}</span>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setShowChangePwd(true)}
                    className="interactive-btn"
                    style={{
                      background: 'transparent', border: 'none',
                      color: 'var(--text-tertiary)', cursor: 'pointer',
                      padding: '1px 3px', display: 'flex',
                    }}
                    title="修改密码"
                  >
                    <LockKey size={10} weight="bold" />
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={logout}
                    className="interactive-btn"
                    style={{
                      background: 'transparent', border: 'none',
                      color: 'var(--text-tertiary)', cursor: 'pointer',
                      padding: '1px 3px', display: 'flex',
                    }}
                    title="退出登录"
                  >
                    <SignOut size={10} weight="bold" />
                  </motion.button>
                </div>
              ) : (
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/login')}
                  className="interactive-btn"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.22)',
                    borderRadius: 'var(--radius-sm)', padding: '1px 8px',
                    color: 'var(--accent)', fontSize: 9,
                    fontFamily: 'var(--font-mono)', cursor: 'pointer',
                  }}
                >
                  <User size={9} weight="bold" />
                  登录
                </motion.button>
              )}
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              <LiveClock />
            </>
          )}
        </div>
      </motion.header>

      {/* Mobile Hamburger Menu */}
      {isMobile && (
        <Suspense fallback={null}>
          <MobileMenu
            show={showMenu}
            onClose={() => setShowMenu(false)}
            onOpenPanel={openPanel}
            onOpenSources={() => { setShowMenu(false); setShowSources(true) }}
            triggerCollect={triggerCollect}
            collecting={collecting}
            totalItems={data?.total_items ?? 0}
            sourcesCount={data?.sources.length ?? 0}
            liveClock={<LiveClock />}
          />
        </Suspense>
      )}

      {/* Mobile Date Navigation */}
      {isMobile && (
        <motion.div
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="glass-panel"
          style={{
            position: 'absolute', top: 52, left: 8, right: 8,
            height: 32, borderRadius: 'var(--radius-md)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            zIndex: 'var(--z-layer-panel)',
            border: '1px solid var(--glass-border)',
          }}
        >
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => navigateDate(-1)}
            disabled={!hasPrevDate}
            style={{
              background: 'transparent', border: 'none',
              color: 'var(--text-tertiary)', cursor: hasPrevDate ? 'pointer' : 'default',
              padding: 4, display: 'flex', opacity: hasPrevDate ? 0.7 : 0.25,
            }}
          >
            <CaretLeft size={12} weight="bold" />
          </motion.button>
          <span style={{
            fontSize: 10, color: 'var(--accent)', fontFamily: 'var(--font-mono)',
            fontWeight: 600, minWidth: 72, textAlign: 'center' as const,
          }}>
            {selectedDate === new Date().toISOString().slice(0, 10)
              ? '今天'
              : selectedDate.slice(5).replace('-', '月') + '日'}
          </span>
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => navigateDate(1)}
            disabled={!hasNextDate}
            style={{
              background: 'transparent', border: 'none',
              color: 'var(--text-tertiary)', cursor: hasNextDate ? 'pointer' : 'default',
              padding: 4, display: 'flex', opacity: hasNextDate ? 0.7 : 0.25,
            }}
          >
            <CaretRight size={12} weight="bold" />
          </motion.button>
          {selectedDate !== new Date().toISOString().slice(0, 10) && (
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={goToToday}
              style={{
                background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.22)',
                color: 'var(--accent)', cursor: 'pointer',
                padding: '2px 8px', borderRadius: 3,
                fontSize: 9, fontFamily: 'var(--font-mono)',
              }}
            >
              今天
            </motion.button>
          )}
        </motion.div>
      )}

      {/* Layer Panel — desktop: left sidebar; mobile: horizontal strip below top bar */}
      {isMobile ? (
        <motion.div
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{ position: 'absolute', top: 88, left: 4, right: 4, zIndex: 'var(--z-layer-panel)' }}
        >
          <div
            className="glass-panel mobile-layer-strip"
            style={{
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--glass-border)',
              boxShadow: 'var(--shadow-diffuse)',
            }}
          >
            {(data?.layers ?? []).map(l => {
              const meta = LAYER_META[l.layer]
              const isActive = activeLayers.has(l.layer)
              return (
                <motion.button
                  key={l.layer}
                  whileTap={{ scale: 0.92 }}
                  onClick={() => toggleLayer(l.layer)}
                  style={{
                    position: 'relative',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: 32, height: 32, flexShrink: 0,
                    border: isActive ? `1px solid ${meta.color}44` : '1px solid transparent',
                    borderRadius: 'var(--radius-sm)',
                    background: isActive ? `${meta.color}18` : 'transparent',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: meta.color,
                    opacity: isActive ? 1 : 0.35,
                    boxShadow: isActive ? `0 0 4px ${meta.color}55` : 'none',
                    transition: 'opacity 0.15s ease',
                  }} />
                  {l.count > 0 && (
                    <span style={{
                      position: 'absolute', top: 1, right: 1,
                      fontSize: 7, fontWeight: 700, color: meta.color,
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {l.count > 99 ? '99+' : l.count}
                    </span>
                  )}
                </motion.button>
              )
            })}
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ x: -40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 100, damping: 20, delay: 0.3 }}
          style={{ position: 'absolute', left: 12, top: 72, zIndex: 'var(--z-layer-panel)' }}
        >
          <LayerPanel layers={data?.layers ?? []} activeLayers={activeLayers} onToggle={toggleLayer} />
        </motion.div>
      )}

      {!isMobile && (
        <CommandSummary
          data={data}
          activeLayerCount={activeLayers.size}
          selectedDate={selectedDate}
          lastUpdated={lastUpdated}
        />
      )}

      {/* Source Panel — desktop: right drawer; mobile: full-screen panel */}
      {data && data.sources.length > 0 && (
        <Suspense fallback={null}>
          <SourcePanel
            sources={data.sources}
            expanded={showSources}
            onToggle={() => setShowSources(!showSources)}
            isMobile={isMobile}
          />
        </Suspense>
      )}

      {/* Bottom Ticker Bar */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="glass-panel"
        style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: isMobile ? 40 : 32, zIndex: 150,
          borderRadius: 0,
          borderTop: '1px solid var(--glass-border)',
          display: 'flex',
        }}
      >
        <motion.div
          whileHover={{ scale: 1.02 }}
          onClick={() => setShowFeeds(!showFeeds)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: isMobile ? '0 10px' : '0 14px',
            cursor: 'pointer',
            borderRight: '1px solid var(--glass-border)',
            fontSize: isMobile ? 10 : 9, color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)', letterSpacing: 1,
            whiteSpace: 'nowrap',
          }}
        >
          <motion.span
            animate={{ opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            style={{
              display: 'inline-block', width: 5, height: 5, borderRadius: '50%',
              background: 'var(--accent)',
              boxShadow: '0 0 6px var(--accent-glow)',
            }}
          />
          情报流 ({mapItems.length})
        </motion.div>

        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}
          onMouseEnter={e => { (e.currentTarget.firstElementChild as HTMLElement | null)?.style.setProperty('animation-play-state', 'paused') }}
          onMouseLeave={e => { (e.currentTarget.firstElementChild as HTMLElement | null)?.style.setProperty('animation-play-state', 'running') }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', gap: 32,
            height: '100%',
            animation: 'ticker-scroll 60s linear infinite',
            whiteSpace: 'nowrap',
          }}>
            {[0, 1].map(copy => (
              <div key={copy} style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
                {mapItems.slice(0, 60).map(item => {
                  const meta = LAYER_META[item.layer]
                  const ctx = analysisContext.itemContext[item.id]
                  const confidence = ctx?.eventConfidenceLevel
                    ? { level: ctx.eventConfidenceLevel, label: ctx.eventConfidenceLabel ?? '' }
                    : itemConfidenceLevel(item)
                  const confidenceText = ctx?.eventId ? `${confidence.level}/${ctx.eventId}` : confidence.level
                  return (
                    <motion.span
                      key={`${item.id}-${copy}`}
                      whileHover={{ color: 'var(--text-primary)' }}
                      onClick={() => setSelectedItem(item)}
                      className="ticker-item"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        fontSize: isMobile ? 11 : 10, color: 'var(--text-tertiary)',
                        cursor: 'pointer', fontFamily: 'var(--font-mono)',
                      }}
                    >
                      <span style={{ color: ctx?.warningSeverity ? warningColor(ctx.warningSeverity) : meta.color, fontSize: isMobile ? 8 : 7 }}>•</span>
                      <span style={{ maxWidth: isMobile ? 100 : 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.title}
                      </span>
                      <span style={{
                        fontSize: isMobile ? 8 : 7, fontWeight: 600,
                        color: confidenceColor(confidence.level),
                      }}>
                        {confidenceText}
                      </span>
                      {!isMobile && (
                        <span style={{ fontSize: 8, color: 'var(--text-tertiary)' }}>
                          {item.country}
                        </span>
                      )}
                    </motion.span>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Expanded Feed Panel */}
      <AnimatePresence>
        {showFeeds && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
            className="glass-panel"
            style={{
              position: 'absolute',
              bottom: isMobile ? 40 : 32,
              left: 0, right: 0,
              height: isMobile ? '50vh' : 200,
              zIndex: 'var(--z-feed-expanded)',
              borderTop: '1px solid var(--glass-border)',
              borderRadius: 0,
              overflow: 'hidden',
            }}
          >
            <Suspense fallback={<InlineModuleFallback label="情报流加载中" />}>
              <MessageFeed
                items={feedFilteredItems}
                onSelect={(item) => { setSelectedItem(item); setShowFeeds(false) }}
                selectedId={selectedItem?.id ?? null}
                contextByItemId={analysisContext.itemContext}
                hasMore={hasMore}
                loadingMore={loadingMore}
                onLoadMore={loadMoreItems}
              />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Overlay Panels — desktop: centered card; mobile: full-screen */}
      <AnimatePresence>
        {selectedItem && (
          <Suspense fallback={null}>
            <IntelCard
              key="intel-card"
              item={selectedItem}
              onClose={() => setSelectedItem(null)}
              isMobile={isMobile}
              analysisContext={analysisContext.itemContext[selectedItem.id]}
              onAnalyzeItem={() => analyzeItem(selectedItem)}
              onAddToBrief={() => addItemToBrief(selectedItem)}
            />
          </Suspense>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'ask' && (
          <Suspense fallback={<InlineModuleFallback label="情报查询加载中" />}>
            <AskPanel key="ask-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />
          </Suspense>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'stats' && (
          <Suspense fallback={<InlineModuleFallback label="看板加载中" />}>
            <StatsPanel key="stats-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />
          </Suspense>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'report' && (
          <Suspense fallback={<InlineModuleFallback label="简报加载中" />}>
            <ReportPanel
              key="report-panel"
              onClose={() => setActivePanel(null)}
              isMobile={isMobile}
              userId={currentUserId}
              workspace={briefWorkspace}
              onRemoveMaterial={removeBriefMaterial}
              onClearWorkspace={clearBriefWorkspace}
            />
          </Suspense>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'analysis' && (
          <Suspense fallback={<InlineModuleFallback label="分析模块加载中" />}>
            <IntelAnalysisPanel
              key="analysis-panel"
              onClose={() => setActivePanel(null)}
              isMobile={isMobile}
              selectedDate={selectedDate}
              startDate={startDate}
              endDate={endDate}
              activeLayers={[...activeLayers]}
              focusItem={analysisFocus?.item ?? null}
              focusEventId={analysisFocus?.eventId}
              onAddToBrief={addBriefMaterial}
            />
          </Suspense>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'super' && (
          <Suspense fallback={<InlineModuleFallback label="超级分析加载中" />}>
            <SuperAnalysisPanel
              key="super-analysis-panel"
              onClose={() => setActivePanel(null)}
              isMobile={isMobile}
              startDate={startDate || selectedDate}
              endDate={endDate || selectedDate}
            />
          </Suspense>
        )}
      </AnimatePresence>

      {/* Error Toast */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -10, opacity: 0 }}
            style={{
              position: 'fixed', top: isMobile ? 56 : 60, left: '50%', transform: 'translateX(-50%)',
              background: 'rgba(217,107,98,0.10)',
              border: '1px solid rgba(217,107,98,0.25)',
              color: 'var(--danger)', padding: isMobile ? '10px 14px' : '8px 16px',
              borderRadius: 'var(--radius-md)',
              zIndex: 'var(--z-overlay)', fontSize: isMobile ? 12 : 11,
              fontFamily: 'var(--font-mono)',
              boxShadow: 'var(--shadow-diffuse)',
              display: 'flex', alignItems: 'center', gap: 12,
              maxWidth: isMobile ? '90vw' : undefined,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)' }} />
            {error}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => loadData()}
              style={{
                background: 'rgba(217,107,98,0.10)', border: '1px solid rgba(217,107,98,0.25)',
                color: 'var(--danger)', padding: '3px 10px', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', fontSize: 10, fontFamily: 'var(--font-mono)',
              }}
            >
              重试
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading Skeleton */}
      <AnimatePresence>
        {loading && (
          <motion.div
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 'var(--z-loading)',
              background: 'var(--bg-deep)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div className="glass-panel" style={{
                margin: isMobile ? 8 : 12, height: 36, borderRadius: 'var(--radius-md)',
                display: 'flex', alignItems: 'center', padding: '0 14px',
              }}>
                <div style={{ ...SHIMMER_STYLE, width: 60, height: 10, borderRadius: 99, animationDuration: '2s' }} />
                <div style={{ flex: 1 }} />
                <div style={{ ...SHIMMER_STYLE, width: 80, height: 10, borderRadius: 99, animationDuration: '2s', animationDelay: '0.2s' }} />
              </div>
              <div style={{ flex: 1, display: 'flex', gap: 12, padding: '0 16px 12px' }}>
                {!isMobile && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: 44 }}>
                    {[...Array(8)].map((_, i) => (
                      <div key={i} style={{
                        ...SKELETON_ITEM_STYLE,
                        opacity: 1 - i * 0.08,
                        animationDelay: `${i * 0.1}s`,
                      }} />
                    ))}
                  </div>
                )}
                <div style={{ ...SKELETON_ITEM_STYLE, flex: 1 }} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Change Password Modal ── */}
      <AnimatePresence>
        {showChangePwd && (
          <ChangePasswordModal
            onClose={() => { setShowChangePwd(false); setChangePwdError('') }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!oldPassword || !newPassword || !confirmPassword) {
      setError('请填写所有字段')
      return
    }
    if (newPassword.length < 6) {
      setError('新密码至少6位')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致')
      return
    }
    setLoading(true)
    try {
      await changePassword(oldPassword, newPassword)
      alert('密码修改成功')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '修改失败')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 14px', fontSize: 14,
    borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)',
    background: 'var(--bg-surface)', color: 'var(--text-primary)',
    outline: 'none', boxSizing: 'border-box',
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
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--glass-bg)',
          backdropFilter: 'blur(24px)',
          border: '1px solid var(--glass-border)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-diffuse)',
          width: '100%', maxWidth: 400, padding: 28,
        }}
      >
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 20px' }}>
          修改密码
        </h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>原密码</label>
            <input type="password" value={oldPassword} onChange={e => setOldPassword(e.target.value)} style={inputStyle} autoFocus />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>新密码（至少6位）</label>
            <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>确认新密码</label>
            <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} style={inputStyle} />
          </div>
          {error && (
            <p style={{ fontSize: 12, color: 'var(--danger)', margin: '0 0 16px' }}>{error}</p>
          )}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <motion.button
              type="button"
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={onClose}
              style={{
                background: 'rgba(236,230,218,0.06)', border: '1px solid var(--glass-border)',
                color: 'var(--text-secondary)', padding: '10px 20px',
                borderRadius: 'var(--radius-md)', cursor: 'pointer',
                fontSize: 13, fontFamily: 'var(--font-mono)',
              }}
            >
              取消
            </motion.button>
            <motion.button
              type="submit"
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              disabled={loading}
              style={{
                background: loading ? 'var(--accent-dim)' : 'var(--accent)',
                border: 'none', borderRadius: 'var(--radius-md)',
                color: loading ? 'var(--text-tertiary)' : 'var(--bg-deep)',
                cursor: loading ? 'not-allowed' : 'pointer',
                padding: '10px 20px', fontSize: 13, fontWeight: 600,
                fontFamily: 'var(--font-mono)',
              }}
            >
              {loading ? '修改中...' : '确认修改'}
            </motion.button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/admin" element={<AdminPanel />} />
        <Route path="/*" element={<Dashboard />} />
      </Routes>
    </Suspense>
  )
}
