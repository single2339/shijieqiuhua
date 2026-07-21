import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, Brain, Article, WarningCircle, ChartBar, Lightning, ArrowsLeftRight,
} from '@phosphor-icons/react'
import type { BriefWorkspaceMaterial, EventCluster, IntelItem, IntelLayer } from '../types'
import { LAYER_META } from '../types'
import SituationBriefView from './analysis/SituationBriefView'
import EventClustersView from './analysis/EventClustersView'
import WarningIndicatorsView from './analysis/WarningIndicatorsView'
import CorroborationView from './analysis/CorroborationView'
import GapAnalysisView from './analysis/GapAnalysisView'
import { buildAnalysisWindow } from '../utils/analysisWindow'
import { itemToBriefMaterial } from '../utils/intelDisplay'
import { useFloatingPanel } from '../hooks/useFloatingPanel'
import { safeExternalUrl } from '../utils/safeUrl'

interface Props {
  onClose: () => void
  isMobile?: boolean
  selectedDate: string
  startDate?: string
  endDate?: string
  activeLayers: IntelLayer[]
  focusItem?: IntelItem | null
  focusEventId?: string
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}

const WORKFLOW_STEPS = [
  { key: 'scope', label: '研判范围', icon: ChartBar },
  { key: 'events', label: '事件核查', icon: Article },
  { key: 'evidence', label: '证据评估', icon: ArrowsLeftRight },
  { key: 'brief', label: '态势研判', icon: Brain },
  { key: 'warnings', label: '预警指标', icon: WarningCircle },
] as const

type StepKey = typeof WORKFLOW_STEPS[number]['key']

export default function IntelAnalysisPanel({
  onClose,
  isMobile,
  selectedDate,
  startDate = '',
  endDate = '',
  activeLayers,
  focusItem = null,
  focusEventId = '',
  onAddToBrief,
}: Props) {
  const [activeStep, setActiveStep] = useState<StepKey>('events')
  const [selectedEvent, setSelectedEvent] = useState<EventCluster | null>(null)

  const periodLabel = startDate || endDate ? `${startDate || '起始'} → ${endDate || '现在'}` : selectedDate
  const analysisWindow = buildAnalysisWindow({
    selectedDate,
    startDate,
    endDate,
    focusDate: focusItem?.captured_at?.slice(0, 10) || '',
  })
  const selectedEventId = selectedEvent?.id ?? focusEventId
  const floating = useFloatingPanel({
    enabled: !isMobile,
    width: 760,
    height: 560,
    anchor: 'bottom-center',
  })

  useEffect(() => {
    if (!focusItem) return
    setActiveStep('events')
    setSelectedEvent(null)
  }, [focusItem?.id])

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
        height: isMobile ? '100%' : 'min(560px, 76vh)',
        maxHeight: isMobile ? '100%' : '76vh',
        borderRadius: isMobile ? 0 : 'var(--radius-lg)',
        zIndex: 'var(--z-panel)', overflow: 'hidden',
        boxShadow: 'var(--shadow-diffuse)',
        fontFamily: 'var(--font-ui)',
        display: 'flex',
        flexDirection: 'column',
        ...floating.panelStyle,
      }}
    >
      <div {...floating.dragHandleProps} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 18px', borderBottom: '1px solid var(--glass-border)',
        flexShrink: 0,
        ...floating.dragHandleStyle,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <ChartBar size={14} weight="duotone" color="var(--accent)" />
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 1, fontFamily: 'var(--font-display)' }}>
            情报分析
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {periodLabel}{focusItem ? ` · 单条情报 ${focusItem.id}` : selectedEventId ? ` · ${selectedEventId}` : ''}
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

      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? 'repeat(5, minmax(76px, 1fr))' : 'repeat(5, minmax(120px, 1fr))',
        gap: 4,
        padding: '9px 14px',
        borderBottom: '1px solid var(--glass-border)',
        overflowX: 'auto',
        flexShrink: 0,
      }}>
        {WORKFLOW_STEPS.map((step, index) => {
          const Icon = step.icon
          const isActive = activeStep === step.key
          const isDone = index < WORKFLOW_STEPS.findIndex(item => item.key === activeStep)
          return (
            <motion.button
              key={step.key}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setActiveStep(step.key)}
              style={{
                display: 'grid',
                gridTemplateColumns: 'auto 1fr',
                alignItems: 'center',
                gap: 6,
                minWidth: isMobile ? 76 : 120,
                padding: '7px 9px',
                background: isActive ? 'var(--accent-dim)' : 'transparent',
                border: isActive ? '1px solid rgba(200,164,93,0.22)' : '1px solid var(--glass-border)',
                borderRadius: 'var(--radius-sm)',
                color: isActive ? 'var(--accent)' : isDone ? 'var(--text-secondary)' : 'var(--text-tertiary)',
                fontSize: 10,
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                textAlign: 'left',
              }}
            >
              <Icon size={13} weight={isActive ? 'fill' : 'duotone'} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{step.label}</span>
            </motion.button>
          )
        })}
      </div>

      <div style={{ padding: '12px 14px', overflowY: 'auto', flex: 1, minHeight: 0 }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeStep}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {activeStep === 'scope' && (
              <ScopeView
                periodLabel={periodLabel}
                analysisWindowLabel={analysisWindow.label}
                analysisWindowIsExplicit={analysisWindow.isExplicit}
                activeLayers={activeLayers}
                focusItem={focusItem}
                selectedEvent={selectedEvent}
                onGoEvents={() => setActiveStep('events')}
                onAddToBrief={onAddToBrief}
              />
            )}
            {activeStep === 'events' && (
              <EventClustersView
                selectedDate={selectedDate}
                startDate={analysisWindow.startDate}
                endDate={analysisWindow.endDate}
                activeLayers={activeLayers}
                selectedClusterId={selectedEventId}
                focusItemId={focusItem?.id}
                onSelectCluster={setSelectedEvent}
              />
            )}
            {activeStep === 'evidence' && (
              <EvidenceAssessmentView
                selectedDate={selectedDate}
                startDate={analysisWindow.startDate}
                endDate={analysisWindow.endDate}
                activeLayers={activeLayers}
                focusItem={focusItem}
                selectedEvent={selectedEvent}
                onAddToBrief={onAddToBrief}
              />
            )}
            {activeStep === 'brief' && (
              <SituationBriefView
                selectedDate={selectedDate}
                startDate={analysisWindow.startDate}
                endDate={analysisWindow.endDate}
                activeLayers={activeLayers}
                onAddToBrief={onAddToBrief}
              />
            )}
            {activeStep === 'warnings' && (
              <WarningIndicatorsView
                selectedDate={selectedDate}
                startDate={analysisWindow.startDate}
                endDate={analysisWindow.endDate}
                activeLayers={activeLayers}
                focusEventId={selectedEventId}
                onAddToBrief={onAddToBrief}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function ScopeView({
  periodLabel,
  analysisWindowLabel,
  analysisWindowIsExplicit,
  activeLayers,
  focusItem,
  selectedEvent,
  onGoEvents,
  onAddToBrief,
}: {
  periodLabel: string
  analysisWindowLabel: string
  analysisWindowIsExplicit: boolean
  activeLayers: IntelLayer[]
  focusItem: IntelItem | null
  selectedEvent: EventCluster | null
  onGoEvents: () => void
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}) {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <Panel>
        <SectionTitle title="处理链路" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
          {['范围定义', '事件归并', '证据复核', '判断形成', '预警处置'].map((item, index) => (
            <div key={item} style={{
              padding: '8px 10px',
              background: 'var(--bg-deep)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-sm)',
            }}>
              <div style={{ fontSize: 8, color: 'var(--accent)', fontFamily: 'var(--font-mono)', marginBottom: 4 }}>
                {String(index + 1).padStart(2, '0')}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-primary)', fontWeight: 700 }}>{item}</div>
            </div>
          ))}
        </div>
      </Panel>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
        <Panel>
          <SectionTitle title="当前范围" />
          <MetaLine label="时间" value={periodLabel} />
          <MetaLine label="事件窗口" value={`${analysisWindowLabel}${analysisWindowIsExplicit ? ' · 手动范围' : ' · 默认14天'}`} />
          <MetaLine label="图层" value={activeLayers.length ? activeLayers.map(layer => LAYER_META[layer]?.label ?? layer).join('、') : '未选择'} />
          <MetaLine label="焦点" value={focusItem ? `单条情报 · ${focusItem.id}` : selectedEvent ? `${selectedEvent.id} · ${selectedEvent.title}` : '全局范围'} />
          {focusItem && (
            <>
              <MetaLine label="来源" value={focusItem.source_system || '未知来源'} />
              <MetaLine label="地区" value={`${focusItem.location_name} · ${focusItem.country}`} />
            </>
          )}
        </Panel>

        <Panel>
          <SectionTitle title="操作焦点" />
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.65, marginBottom: 10 }}>
            {focusItem
              ? '当前以单条情报为焦点。先确认它是否已归入事件簇，再进入证据评估、态势研判和预警指标。'
              : '先在事件核查中选定事件簇，再进入证据评估、态势研判和预警指标。未选定事件时，各步骤使用全局范围。'}
          </div>
          <button
            onClick={onGoEvents}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 10px',
              border: '1px solid rgba(200,164,93,0.24)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--accent-dim)',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
            }}
          >
            <Article size={12} weight="duotone" />
            进入事件核查
          </button>
          {(focusItem || selectedEvent) && onAddToBrief && (
            <button
              onClick={() => onAddToBrief(focusItem ? itemToBriefMaterial(focusItem, '情报分析') : eventToBriefMaterial(selectedEvent!))}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '6px 10px', marginLeft: 8,
                border: '1px solid var(--glass-border)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-deep)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
              }}
            >
              <Article size={12} weight="duotone" />
              加入简报候选
            </button>
          )}
        </Panel>
      </div>
    </div>
  )
}

function EvidenceAssessmentView({
  selectedDate,
  startDate,
  endDate,
  activeLayers,
  focusItem,
  selectedEvent,
  onAddToBrief,
}: {
  selectedDate: string
  startDate: string
  endDate: string
  activeLayers: IntelLayer[]
  focusItem: IntelItem | null
  selectedEvent: EventCluster | null
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}) {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {focusItem && (
        <Panel>
          <SectionTitle title="单条情报" />
          <div style={{ display: 'grid', gap: 6 }}>
            <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.45 }}>
              {focusItem.title}
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {focusItem.id} · {focusItem.source_system || '未知来源'} · {focusItem.location_name} · {focusItem.captured_at?.slice(0, 10) || '未知时间'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
              {focusItem.summary}
            </div>
            {onAddToBrief && (
              <ActionButton label="将该情报加入简报" onClick={() => onAddToBrief(itemToBriefMaterial(focusItem, '情报分析'))} />
            )}
          </div>
        </Panel>
      )}

      <Panel>
        <SectionTitle title="证据焦点" />
        {selectedEvent ? (
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <Lightning size={15} weight="duotone" color="var(--accent)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>{selectedEvent.title}</div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>
                  {selectedEvent.id} · {selectedEvent.item_count} 条 · {selectedEvent.source_count} 源 · {selectedEvent.confidence.level} {selectedEvent.confidence.label}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{selectedEvent.summary}</div>
            {onAddToBrief && (
              <ActionButton label="将该事件加入简报" onClick={() => onAddToBrief(eventToBriefMaterial(selectedEvent))} />
            )}
            <div style={{ display: 'grid', gap: 5 }}>
              {selectedEvent.evidence.slice(0, 8).map(evidence => {
                const evidenceUrl = safeExternalUrl(evidence.url)
                if (!evidenceUrl) return null
                return (
                <a
                  key={evidence.id}
                  href={evidenceUrl}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'grid', gridTemplateColumns: '42px 1fr auto', gap: 8,
                    padding: '7px 9px', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
                    textDecoration: 'none',
                  }}
                >
                  <span style={{ fontSize: 9, color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{evidence.id}</span>
                  <span style={{ minWidth: 0 }}>
                    <span style={{ display: 'block', fontSize: 10, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {evidence.title}
                    </span>
                    <span style={{ display: 'block', fontSize: 8, color: 'var(--text-tertiary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {evidence.source} · {evidence.country || '未知地区'}
                    </span>
                  </span>
                  <span style={{ fontSize: 8, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {evidence.confidence_level}
                  </span>
                </a>
                )
              })}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.65 }}>
            尚未选择事件簇。下方显示当前范围的信源独立性和采集缺口，选择事件后会聚焦到具体证据链。
          </div>
        )}
      </Panel>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12 }}>
        <Panel>
          <SectionTitle title="信源独立性" />
          <CorroborationView
            selectedDate={selectedDate}
            startDate={startDate}
            endDate={endDate}
            activeLayers={activeLayers}
          />
        </Panel>
        <Panel>
          <SectionTitle title="补采与待核查" />
          <GapAnalysisView
            selectedDate={selectedDate}
            startDate={startDate}
            endDate={endDate}
            activeLayers={activeLayers}
          />
        </Panel>
      </div>
    </div>
  )
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, fontFamily: 'var(--font-mono)' }}>
      {title}
    </div>
  )
}

function ActionButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        justifySelf: 'start',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 10px',
        border: '1px solid rgba(200,164,93,0.24)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--accent-dim)',
        color: 'var(--accent)',
        cursor: 'pointer',
        fontSize: 10,
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
      }}
    >
      <Article size={12} weight="duotone" />
      {label}
    </button>
  )
}

function eventToBriefMaterial(event: EventCluster): BriefWorkspaceMaterial {
  const sources = [...new Set(event.evidence.flatMap(evidence => [evidence.source, ...(evidence.sources ?? [])]).filter(Boolean))]
  return {
    id: event.id,
    type: 'event',
    title: event.title,
    summary: event.summary,
    source: sources[0] || `${event.source_count}源`,
    sources,
    date: event.start_date === event.end_date ? event.start_date : `${event.start_date || '未知'} → ${event.end_date || '现在'}`,
    layer: event.layers.join(','),
    country: event.countries.join(','),
    confidence_level: `${event.confidence.level} ${event.confidence.label}`,
    origin: '事件核查',
  }
}

function Panel({ children }: { children: ReactNode }) {
  return (
    <div style={{
      padding: '12px 14px',
      background: 'rgba(32,36,40,0.72)',
      border: '1px solid var(--glass-border)',
      borderRadius: 'var(--radius-md)',
      minWidth: 0,
    }}>
      {children}
    </div>
  )
}

function MetaLine({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '52px 1fr', gap: 8, fontSize: 10, lineHeight: 1.6, marginBottom: 4 }}>
      <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{label}</span>
      <span style={{ color: 'var(--text-secondary)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  )
}
