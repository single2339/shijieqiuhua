import { useEffect, useState, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { MagnifyingGlass, FileText, ChartBar, ArrowsClockwise, Database, Rows, MapPin, Brain, List, CaretLeft, CaretRight, User, SignOut, Gear } from '@phosphor-icons/react'
import type { IntelItem, IntelLayer, DashboardData } from './types'
import { LAYER_META } from './types'
import { useAuth } from './contexts/AuthContext'
import { useIsMobile } from './hooks/useMediaQuery'
import { useDashboardData } from './hooks/useDashboardData'
import MapView from './components/MapView'
import LayerPanel from './components/LayerPanel'
import IntelCard from './components/IntelCard'
import MessageFeed from './components/MessageFeed'
import AskPanel from './components/AskPanel'
import StatsPanel from './components/StatsPanel'
import ReportPanel from './components/ReportPanel'
import SourcePanel from './components/SourcePanel'
import IntelAnalysisPanel from './components/IntelAnalysisPanel'
import SuperAnalysisPanel from './components/SuperAnalysisPanel'
import MobileMenu from './components/MobileMenu'
import StatusDot from './components/StatusDot'
import LoginPage from './components/LoginPage'
import RegisterPage from './components/RegisterPage'
import AdminPanel from './components/AdminPanel'

const ALL_LAYERS: IntelLayer[] = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber']

const SHIMMER_STYLE: React.CSSProperties = {
  backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(0,0,0,0.04) 50%, var(--bg-elevated) 75%)',
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.5s ease-in-out infinite',
}

const SKELETON_ITEM_STYLE: React.CSSProperties = {
  height: 40, borderRadius: 'var(--radius-md)',
  background: 'var(--bg-elevated)',
  backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(0,0,0,0.03) 50%, var(--bg-elevated) 75%)',
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

function Dashboard() {
  const isMobile = useIsMobile()
  const { user, isAuthenticated, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [activeLayers, setActiveLayers] = useState<Set<IntelLayer>>(new Set(ALL_LAYERS))
  const [selectedItem, setSelectedItem] = useState<IntelItem | null>(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10))
  const [activePanel, setActivePanel] = useState<string | null>(null)
  const [showFeeds, setShowFeeds] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const [showMenu, setShowMenu] = useState(false)

  const {
    data, loading, error, lastUpdated, collecting,
    feedPage, feedItems, loadingMore,
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

  const mapItems = useMemo(() => (data?.intel_items ?? []).filter(i => activeLayers.has(i.layer)), [data?.intel_items, activeLayers])
  const feedFilteredItems = useMemo(() => feedItems.filter(i => activeLayers.has(i.layer)), [feedItems, activeLayers])

  const openPanel = (panel: string) => { setShowMenu(false); setActivePanel(panel) }

  return (
    <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', background: 'var(--bg-deep)', position: 'relative' }}>
      {/* Full-screen Map */}
      <div style={{ position: 'absolute', inset: 0 }}>
        {!loading && <MapView items={mapItems} onSelect={setSelectedItem} />}
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
          left: isMobile ? 8 : 60, right: isMobile ? 8 : 12,
          height: isMobile ? 40 : 36,
          borderRadius: 'var(--radius-md)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: isMobile ? '0 8px 0 10px' : '0 10px 0 14px',
          zIndex: 'var(--z-top-bar)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 6 : 14 }}>
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            style={{ fontSize: isMobile ? 11 : 10, color: 'var(--accent)', letterSpacing: isMobile ? 2 : 4, fontWeight: 700 }}
          >
            OSINT
          </motion.span>
          {!isMobile && (
            <>
              <span style={{ width: 1, height: 12, background: 'var(--border-subtle)' }} />
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)', letterSpacing: 1, fontFamily: 'var(--font-ui)' }}>
                全球情报指挥系统
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
                    background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.15)',
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
                onClick={() => setActivePanel('ask')}
                className="interactive-btn"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(16,185,129,0.15)',
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
                  background: 'rgba(16,185,129,0.06)',
                  border: collecting ? '1px solid transparent' : '1px solid rgba(16,185,129,0.2)',
                  borderRadius: 'var(--radius-sm)',
                  color: collecting ? 'var(--text-tertiary)' : 'var(--accent)',
                  cursor: collecting ? 'default' : 'pointer',
                  padding: '2px 8px', fontSize: 9,
                  fontFamily: 'var(--font-mono)', opacity: collecting ? 0.6 : 1,
                }}
              >
                {collecting ? '采集中...' : '+采集'}
              </motion.button>
              <ActionBtn icon={<ChartBar size={10} weight="duotone" />} label="看板" onClick={() => setActivePanel('stats')} />
              <ActionBtn icon={<FileText size={10} weight="duotone" />} label="简报" onClick={() => setActivePanel('report')} />
              <ActionBtn icon={<Brain size={10} weight="duotone" />} label="超级" onClick={() => setActivePanel('super')} accent />
              <ActionBtn icon={<ChartBar size={10} weight="duotone" />} label="分析" onClick={() => setActivePanel('analysis')} />
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
                    background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
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
                    background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)',
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
                background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.15)',
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
          style={{ position: 'absolute', left: 8, top: 56, zIndex: 'var(--z-layer-panel)' }}
        >
          <LayerPanel layers={data?.layers ?? []} activeLayers={activeLayers} onToggle={toggleLayer} />
        </motion.div>
      )}

      {/* Source Panel — desktop: right drawer; mobile: full-screen panel */}
      {data?.sources && (
        <SourcePanel
          sources={data.sources}
          expanded={showSources}
          onToggle={() => setShowSources(!showSources)}
          isMobile={isMobile}
        />
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
                  const pct = Math.round(item.confidence * 100)
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
                      <span style={{ color: meta.color, fontSize: isMobile ? 8 : 7 }}>•</span>
                      <span style={{ maxWidth: isMobile ? 100 : 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.title}
                      </span>
                      <span style={{
                        fontSize: isMobile ? 8 : 7, fontWeight: 600,
                        color: pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)',
                      }}>
                        {pct}%
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
            <MessageFeed
              items={feedFilteredItems}
              onSelect={(item) => { setSelectedItem(item); setShowFeeds(false) }}
              selectedId={selectedItem?.id ?? null}
              hasMore={data?.has_more ?? false}
              loadingMore={loadingMore}
              onLoadMore={loadMoreItems}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Overlay Panels — desktop: centered card; mobile: full-screen */}
      <AnimatePresence>
        {selectedItem && (
          <IntelCard
            key="intel-card"
            item={selectedItem}
            onClose={() => setSelectedItem(null)}
            isMobile={isMobile}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'ask' && <AskPanel key="ask-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'stats' && <StatsPanel key="stats-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'report' && <ReportPanel key="report-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'analysis' && <IntelAnalysisPanel key="analysis-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />}
      </AnimatePresence>

      <AnimatePresence>
        {activePanel === 'super' && <SuperAnalysisPanel key="super-analysis-panel" onClose={() => setActivePanel(null)} isMobile={isMobile} />}
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
              background: 'rgba(220,38,38,0.08)',
              border: '1px solid rgba(220,38,38,0.25)',
              color: 'var(--danger)', padding: isMobile ? '10px 14px' : '8px 16px',
              borderRadius: 'var(--radius-md)',
              zIndex: 'var(--z-overlay)', fontSize: isMobile ? 12 : 11,
              fontFamily: 'var(--font-mono)',
              boxShadow: '0 0 20px rgba(220,38,38,0.1)',
              display: 'flex', alignItems: 'center', gap: 12,
              maxWidth: isMobile ? '90vw' : undefined,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)', boxShadow: '0 0 6px rgba(220,38,38,0.4)' }} />
            {error}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => loadData()}
              style={{
                background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.25)',
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
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/admin" element={<AdminPanel />} />
      <Route path="/*" element={<Dashboard />} />
    </Routes>
  )
}
