import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, Clock, Graph, ArrowsLeftRight,
  Warning, ChartBar, Lightning,
} from '@phosphor-icons/react'
import TimelineView from './analysis/TimelineView'
import EntityGraphView from './analysis/EntityGraphView'
import CorroborationView from './analysis/CorroborationView'
import AnomalyView from './analysis/AnomalyView'
import RiskHeatmapView from './analysis/RiskHeatmapView'
import GapAnalysisView from './analysis/GapAnalysisView'

interface Props { onClose: () => void; isMobile?: boolean }

const TABS = [
  { key: 'timeline', label: '时间线', icon: Clock },
  { key: 'entity', label: '关联网络', icon: Graph },
  { key: 'corroboration', label: '交叉信源', icon: ArrowsLeftRight },
  { key: 'anomaly', label: '异常检测', icon: Warning },
  { key: 'risk', label: '风险热力', icon: ChartBar },
  { key: 'gap', label: '情报缺口', icon: Lightning },
] as const

type TabKey = typeof TABS[number]['key']

export default function IntelAnalysisPanel({ onClose, isMobile }: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>('timeline')

  return (
    <motion.div
      initial={{ y: 20, opacity: 0, scale: 0.97 }}
      animate={{ y: 0, opacity: 1, scale: 1 }}
      exit={{ y: 20, opacity: 0, scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      className={isMobile ? 'glass-panel mobile-full-panel' : 'glass-panel'}
      style={{
        position: 'fixed',
        bottom: isMobile ? 0 : 16,
        left: isMobile ? 0 : '50%',
        transform: isMobile ? 'none' : 'translateX(-50%)',
        width: isMobile ? '100%' : 760,
        maxWidth: isMobile ? '100%' : '94vw',
        maxHeight: isMobile ? '100%' : '82vh',
        borderRadius: isMobile ? 0 : 'var(--radius-lg)',
        zIndex: 'var(--z-panel)', overflow: 'hidden',
        boxShadow: 'var(--shadow-diffuse)',
        fontFamily: 'var(--font-ui)',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 18px', borderBottom: '1px solid var(--glass-border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ChartBar size={14} weight="duotone" color="var(--accent)" />
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 1, fontFamily: 'var(--font-display)' }}>
            情报分析
          </span>
        </div>
        <motion.button
          whileHover={{ scale: 1.1, rotate: 90 }}
          whileTap={{ scale: 0.9 }}
          onClick={onClose}
          className="interactive-btn"
          style={{
            background: 'rgba(0,0,0,0.04)', border: '1px solid var(--glass-border)',
            color: 'var(--text-tertiary)', cursor: 'pointer',
            width: 28, height: 28, borderRadius: 'var(--radius-sm)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}
        >
          <X size={12} weight="bold" />
        </motion.button>
      </div>

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 2,
        padding: '8px 14px', borderBottom: '1px solid var(--glass-border)',
        overflowX: 'auto',
      }}>
        {TABS.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.key
          return (
            <motion.button
              key={tab.key}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setActiveTab(tab.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 12px',
                background: isActive ? 'rgba(16,185,129,0.08)' : 'transparent',
                border: isActive ? '1px solid rgba(16,185,129,0.2)' : '1px solid transparent',
                borderRadius: 'var(--radius-sm)',
                color: isActive ? 'var(--accent)' : 'var(--text-tertiary)',
                fontSize: 10, fontWeight: isActive ? 600 : 400,
                cursor: 'pointer', fontFamily: 'var(--font-mono)',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={12} weight={isActive ? 'fill' : 'duotone'} />
              {tab.label}
            </motion.button>
          )
        })}
      </div>

      {/* Content */}
      <div style={{
        padding: '14px 18px', overflowY: 'auto', maxHeight: 'calc(82vh - 100px)',
      }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {activeTab === 'timeline' && <TimelineView />}
            {activeTab === 'entity' && <EntityGraphView />}
            {activeTab === 'corroboration' && <CorroborationView />}
            {activeTab === 'anomaly' && <AnomalyView />}
            {activeTab === 'risk' && <RiskHeatmapView />}
            {activeTab === 'gap' && <GapAnalysisView />}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  )
}
