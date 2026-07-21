import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, HTMLAttributes } from 'react'
import { motion } from 'framer-motion'
import {
  Article,
  ArrowsClockwise,
  ClockCounterClockwise,
  DownloadSimple,
  FileText,
  FloppyDisk,
  Trash,
  X,
} from '@phosphor-icons/react'
import { generateReportIntel } from '../api'
import type {
  BriefReportHistoryEntry,
  BriefWorkspace,
  BriefWorkspaceMaterial,
  IntelLayer,
  ReportDraftStatus,
  SituationReport,
} from '../types'
import { LAYER_META } from '../types'
import { useFloatingPanel } from '../hooks/useFloatingPanel'
import { BRIEF_REPORT_HISTORY_STORAGE_KEY, getUserStorageKey } from '../utils/userStorage'

interface Props {
  onClose: () => void
  isMobile?: boolean
  userId: number | null
  workspace: BriefWorkspace
  onRemoveMaterial: (type: BriefWorkspaceMaterial['type'], id: string) => void
  onClearWorkspace: () => void
}

const ALL_LAYERS: IntelLayer[] = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber']
const DETAIL_LEVELS = [
  { value: 'brief', label: '简报' },
  { value: 'standard', label: '标准' },
  { value: 'deep', label: '深度' },
]
const STATUS_LABEL: Record<ReportDraftStatus, string> = {
  draft: '草稿',
  review: '复核',
  published: '发布',
}
const TYPE_LABEL: Record<BriefWorkspaceMaterial['type'], string> = {
  item: '情报',
  event: '事件',
  judgment: '判断',
  warning: '预警',
}

export default function ReportPanel({
  onClose,
  isMobile,
  userId,
  workspace,
  onRemoveMaterial,
  onClearWorkspace,
}: Props) {
  const [topic, setTopic] = useState('')
  const [country, setCountry] = useState('')
  const [days, setDays] = useState(14)
  const [layer, setLayer] = useState('')
  const [detail, setDetail] = useState('standard')
  const [status, setStatus] = useState<ReportDraftStatus>('draft')
  const [report, setReport] = useState<SituationReport | null>(null)
  const [history, setHistory] = useState<BriefReportHistoryEntry[]>(() => loadHistory(userId))
  const [historyOwner, setHistoryOwner] = useState<number | null>(userId)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const floating = useFloatingPanel({
    enabled: !isMobile,
    width: 820,
    height: 620,
    anchor: 'bottom-center',
  })

  const materialCount = workspace.materials.length
  const sourceCount = useMemo(() => countSources(workspace.materials), [workspace.materials])
  const inferredTopic = workspace.materials[0]?.title ?? ''

  // Autofill only reacts to material changes; depending on the field values
  // here would refill a field the moment the user clears it.
  useEffect(() => {
    if (!workspace.materials.length) return
    const first = workspace.materials[0]?.title ?? ''
    if (first) setTopic(prev => prev || first)
    const countries = [...new Set(workspace.materials.map(item => item.country).filter(Boolean))]
    if (countries.length === 1) setCountry(prev => prev || (countries[0] ?? ''))
    const layers = [...new Set(workspace.materials.map(item => item.layer).filter(Boolean))]
    if (layers.length === 1 && ALL_LAYERS.includes(layers[0] as IntelLayer)) {
      setLayer(prev => prev || (layers[0] ?? ''))
    }
  }, [workspace.materials])

  useEffect(() => {
    if (historyOwner !== userId) return
    const storageKey = getUserStorageKey(BRIEF_REPORT_HISTORY_STORAGE_KEY, userId)
    if (!storageKey) return
    window.localStorage.setItem(storageKey, JSON.stringify(history.slice(0, 12)))
  }, [history, historyOwner, userId])

  useEffect(() => {
    setHistory(loadHistory(userId))
    setHistoryOwner(userId)
    setReport(null)
  }, [userId])

  const markdown = useMemo(() => reportToMarkdown(report, workspace.materials), [report, workspace.materials])

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const nextReport = await generateReportIntel({
        topic: topic || inferredTopic || undefined,
        country: country || undefined,
        days,
        layer: layer || undefined,
        detail_level: detail,
        item_ids: workspace.materials.filter(item => item.type === 'item').map(item => item.id),
        event_ids: workspace.materials.filter(item => item.type === 'event').map(item => item.id),
        warning_ids: workspace.materials.filter(item => item.type === 'warning').map(item => item.id),
        source_materials: workspace.materials,
      })
      setReport(nextReport)
      setHistory(prev => [historyEntry(nextReport, workspace.materials, status), ...prev].slice(0, 12))
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
  }

  const saveCurrent = () => {
    if (!report) return
    setHistory(prev => [historyEntry(report, workspace.materials, status), ...prev].slice(0, 12))
  }

  const exportMarkdown = () => {
    if (!report) return
    downloadFile(`${safeName(report.title)}.md`, markdown, 'text/markdown;charset=utf-8')
  }

  const exportHtml = () => {
    if (!report) return
    downloadFile(`${safeName(report.title)}.html`, markdownToHtml(report.title, markdown), 'text/html;charset=utf-8')
  }

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
        width: isMobile ? '100%' : 820,
        maxWidth: isMobile ? '100%' : '94vw',
        height: isMobile ? '100%' : 'min(620px, 78vh)',
        maxHeight: isMobile ? '100%' : '78vh',
        borderRadius: isMobile ? 0 : 'var(--radius-lg)',
        zIndex: 'var(--z-panel)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-diffuse)',
        fontFamily: 'var(--font-ui)',
        ...floating.panelStyle,
      }}
    >
      <Header
        onClose={onClose}
        materialCount={materialCount}
        sourceCount={sourceCount}
        dragHandleProps={floating.dragHandleProps}
        dragHandleStyle={floating.dragHandleStyle}
      />

      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : '300px 1fr',
        gap: 0,
        height: isMobile ? 'calc(100dvh - 52px)' : 'calc(100% - 52px)',
        overflow: 'hidden',
      }}>
        <aside style={{
          padding: '14px 16px',
          borderRight: isMobile ? 'none' : '1px solid var(--glass-border)',
          borderBottom: isMobile ? '1px solid var(--glass-border)' : 'none',
          overflowY: 'auto',
        }}>
          <SectionTitle title="候选材料" aside={`${materialCount}项`} />
          {workspace.materials.length === 0 ? (
            <EmptyNote text="从情报卡片或情报分析中加入材料后，再生成简报。" />
          ) : (
            <div style={{ display: 'grid', gap: 7, marginBottom: 12 }}>
              {workspace.materials.map(material => (
                <MaterialRow key={`${material.type}-${material.id}`} material={material} onRemove={onRemoveMaterial} />
              ))}
            </div>
          )}

          {workspace.materials.length > 0 && (
            <button
              onClick={onClearWorkspace}
              style={secondaryButtonStyle('var(--danger)')}
            >
              <Trash size={12} weight="duotone" />
              清空候选
            </button>
          )}

          <div style={{ height: 14 }} />
          <SectionTitle title="生成参数" />
          <div style={{ display: 'grid', gap: 8 }}>
            <input value={topic} onChange={e => setTopic(e.target.value)} className="panel-input" placeholder="主题" style={inputStyle} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 96px', gap: 8 }}>
              <input value={country} onChange={e => setCountry(e.target.value)} className="panel-input" placeholder="国家/地区" style={inputStyle} />
              <select value={days} onChange={e => setDays(Number(e.target.value))} className="panel-select" style={selectStyle}>
                {[7, 14, 30, 60].map(n => <option key={n} value={n}>{n}天</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 94px 84px', gap: 8 }}>
              <select value={layer} onChange={e => setLayer(e.target.value)} className="panel-select" style={selectStyle}>
                <option value="">全部图层</option>
                {ALL_LAYERS.map(l => <option key={l} value={l}>{LAYER_META[l].label}</option>)}
              </select>
              <select value={detail} onChange={e => setDetail(e.target.value)} className="panel-select" style={selectStyle}>
                {DETAIL_LEVELS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
              <select value={status} onChange={e => setStatus(e.target.value as ReportDraftStatus)} className="panel-select" style={selectStyle}>
                {Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <button onClick={handleGenerate} disabled={loading} style={primaryButtonStyle(loading)}>
              <ArrowsClockwise size={14} weight="bold" />
              {loading ? '生成中...' : '生成简报'}
            </button>
          </div>

          {error && <div style={{ color: 'var(--danger)', fontSize: 10, lineHeight: 1.5, marginTop: 10 }}>{error}</div>}
        </aside>

        <main style={{ padding: '14px 18px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap' }}>
            <SectionTitle title="草稿" aside={report ? STATUS_LABEL[status] : '未生成'} />
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button onClick={saveCurrent} disabled={!report} style={toolbarButtonStyle(!report)}>
                <FloppyDisk size={12} weight="duotone" />
                保存草稿
              </button>
              <button onClick={exportMarkdown} disabled={!report} style={toolbarButtonStyle(!report)}>
                <DownloadSimple size={12} weight="duotone" />
                导出 Markdown
              </button>
              <button onClick={exportHtml} disabled={!report} style={toolbarButtonStyle(!report)}>
                <DownloadSimple size={12} weight="duotone" />
                导出 HTML
              </button>
            </div>
          </div>

          {!report && !loading && (
            <EmptyNote text="先确认候选材料和生成参数。生成后这里会形成可保存、可导出的简报草稿。" />
          )}
          {loading && <LoadingNote />}
          {report && <ReportDraft report={report} />}

          <div style={{ height: 14 }} />
          <SectionTitle title="历史" aside={`${history.length}份`} />
          {history.length === 0 ? (
            <EmptyNote text="生成或保存后的简报会保留在本机历史中。" />
          ) : (
            <div style={{ display: 'grid', gap: 7 }}>
              {history.map(entry => (
                <button
                  key={entry.id}
                  onClick={() => {
                    setReport(entry.report)
                    setStatus(entry.status)
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '8px 10px',
                    background: 'var(--bg-deep)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ClockCounterClockwise size={12} weight="duotone" color="var(--accent)" />
                    <span style={{ fontSize: 10, color: 'var(--text-primary)', fontWeight: 700 }}>{entry.report.title}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 8, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                      {STATUS_LABEL[entry.status]}
                    </span>
                  </div>
                  <div style={{ marginTop: 3, fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                    {entry.saved_at.slice(0, 16).replace('T', ' ')} · {entry.materials.length}项材料
                  </div>
                </button>
              ))}
            </div>
          )}
        </main>
      </div>
    </motion.div>
  )
}

function Header({
  onClose,
  materialCount,
  sourceCount,
  dragHandleProps = {},
  dragHandleStyle = {},
}: {
  onClose: () => void
  materialCount: number
  sourceCount: number
  dragHandleProps?: HTMLAttributes<HTMLDivElement>
  dragHandleStyle?: CSSProperties
}) {
  return (
    <div {...dragHandleProps} style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '14px 18px',
      borderBottom: '1px solid var(--glass-border)',
      ...dragHandleStyle,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <Article size={16} weight="duotone" color="var(--accent)" />
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 1, fontFamily: 'var(--font-display)' }}>
          简报工作台
        </span>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          候选 {materialCount} · 来源 {sourceCount}
        </span>
      </div>
      <motion.button whileHover={{ scale: 1.1, rotate: 90 }} whileTap={{ scale: 0.9 }} onClick={onClose} className="interactive-btn" style={closeStyle}>
        <X size={12} weight="bold" />
      </motion.button>
    </div>
  )
}

function MaterialRow({ material, onRemove }: { material: BriefWorkspaceMaterial; onRemove: Props['onRemoveMaterial'] }) {
  return (
    <div style={{
      padding: '8px 9px',
      background: 'var(--bg-deep)',
      border: '1px solid var(--glass-border)',
      borderRadius: 'var(--radius-sm)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 8, color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 800 }}>
          {TYPE_LABEL[material.type]}
        </span>
        {material.confidence_level && (
          <span style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{material.confidence_level}</span>
        )}
        <button onClick={() => onRemove(material.type, material.id)} style={iconButtonStyle} title="移除">
          <X size={9} weight="bold" />
        </button>
      </div>
      <div style={{
        fontSize: 10,
        color: 'var(--text-primary)',
        lineHeight: 1.45,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
      }}>
        {material.title}
      </div>
      <div style={{ marginTop: 4, fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {material.origin || '候选'} · {material.date || '未知时间'} · {material.source || material.sources?.[0] || '未知来源'}
      </div>
    </div>
  )
}

function ReportDraft({ report }: { report: SituationReport }) {
  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 10px',
        background: 'var(--bg-deep)',
        border: '1px solid var(--glass-border)',
        borderRadius: 'var(--radius-sm)',
        marginBottom: 10,
        fontSize: 9,
        color: 'var(--text-tertiary)',
        fontFamily: 'var(--font-mono)',
      }}>
        <FileText size={12} weight="duotone" color="var(--accent)" />
        <span style={{ color: 'var(--text-secondary)' }}>{report.title}</span>
        <span style={{ marginLeft: 'auto' }}>情报 {report.item_count} · 来源 {report.source_count}</span>
      </div>
      <div style={{
        padding: '12px 14px',
        background: 'var(--accent-dim)',
        border: '1px solid rgba(200,164,93,0.18)',
        borderRadius: 'var(--radius-md)',
        fontSize: 11,
        lineHeight: 1.7,
        color: 'var(--text-primary)',
        marginBottom: 10,
      }}>
        {report.summary}
      </div>
      {report.sections.map((section, index) => (
        <div key={`${section.heading}-${index}`} style={{
          padding: '10px 12px',
          marginBottom: 8,
          background: 'rgba(32,36,40,0.72)',
          border: '1px solid var(--glass-border)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 700, marginBottom: 6 }}>
            {section.heading.replace(/^#+\s*/g, '')}
          </div>
          <div style={{ fontSize: 11, lineHeight: 1.65, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
            {section.body}
          </div>
        </div>
      ))}
    </div>
  )
}

function LoadingNote() {
  return (
    <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
        style={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          border: '2px solid var(--border-subtle)',
          borderTopColor: 'var(--accent)',
          margin: '0 auto 12px',
        }}
      />
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>正在将候选材料整理为简报...</span>
    </div>
  )
}

function SectionTitle({ title, aside }: { title: string; aside?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
      <span style={{ fontSize: 10, fontWeight: 800, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{title}</span>
      {aside && <span style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{aside}</span>}
    </div>
  )
}

function EmptyNote({ text }: { text: string }) {
  return (
    <div style={{
      padding: '16px 14px',
      border: '1px dashed var(--border-subtle)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-tertiary)',
      fontSize: 10,
      lineHeight: 1.6,
      textAlign: 'center',
    }}>
      {text}
    </div>
  )
}

function loadHistory(userId: number | null): BriefReportHistoryEntry[] {
  const storageKey = getUserStorageKey(BRIEF_REPORT_HISTORY_STORAGE_KEY, userId)
  if (!storageKey || typeof window === 'undefined') return []

  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function countSources(materials: BriefWorkspaceMaterial[]) {
  const sources = new Set<string>()
  for (const material of materials) {
    if (material.source) sources.add(material.source)
    for (const source of material.sources ?? []) {
      if (source) sources.add(source)
    }
  }
  return sources.size
}

function historyEntry(report: SituationReport, materials: BriefWorkspaceMaterial[], status: ReportDraftStatus): BriefReportHistoryEntry {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    status,
    saved_at: new Date().toISOString(),
    report,
    materials,
  }
}

function reportToMarkdown(report: SituationReport | null, materials: BriefWorkspaceMaterial[]) {
  if (!report) return ''
  const lines = [
    `# ${report.title}`,
    '',
    `生成时间: ${report.generated_at}`,
    `材料: ${materials.length} 项`,
    '',
    '## 摘要',
    report.summary,
    '',
    ...report.sections.flatMap(section => [
      section.heading.startsWith('#') ? section.heading : `## ${section.heading}`,
      section.body,
      '',
    ]),
    '## 候选材料',
    ...materials.map(material => `- [${TYPE_LABEL[material.type]}] ${material.title} (${material.source || material.sources?.[0] || '未知来源'} / ${material.date || '未知时间'})`),
  ]
  return lines.join('\n')
}

function markdownToHtml(title: string, markdown: string) {
  const body = markdown
    .split('\n')
    .map(line => {
      if (line.startsWith('# ')) return `<h1>${escapeHtml(line.slice(2))}</h1>`
      if (line.startsWith('## ')) return `<h2>${escapeHtml(line.slice(3))}</h2>`
      if (line.startsWith('- ')) return `<p>${escapeHtml(line)}</p>`
      return line ? `<p>${escapeHtml(line)}</p>` : ''
    })
    .join('\n')
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:840px;margin:40px auto;line-height:1.7;color:#202428}h1,h2{line-height:1.3}</style></head><body>${body}</body></html>`
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] ?? char))
}

function safeName(value: string) {
  return value.replace(/[\\/:*?"<>|]+/g, '-').slice(0, 80) || 'situation-brief'
}

function downloadFile(name: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

const inputStyle: React.CSSProperties = {
  background: 'var(--bg-deep)',
  border: '1px solid var(--border-subtle)',
  color: 'var(--text-primary)',
  padding: '7px 10px',
  borderRadius: 'var(--radius-sm)',
  fontSize: 11,
  fontFamily: 'var(--font-ui)',
  outline: 'none',
  minWidth: 0,
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  fontFamily: 'var(--font-mono)',
}

const closeStyle: React.CSSProperties = {
  background: 'rgba(0,0,0,0.04)',
  border: '1px solid var(--glass-border)',
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
  width: 28,
  height: 28,
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}

const iconButtonStyle: React.CSSProperties = {
  marginLeft: 'auto',
  background: 'transparent',
  border: 'none',
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
  display: 'flex',
  padding: 2,
}

function primaryButtonStyle(disabled: boolean): React.CSSProperties {
  return {
    background: disabled ? 'var(--bg-elevated)' : 'var(--accent)',
    border: 'none',
    color: disabled ? 'var(--text-tertiary)' : 'var(--bg-deep)',
    padding: '9px 0',
    borderRadius: 'var(--radius-sm)',
    cursor: disabled ? 'default' : 'pointer',
    fontSize: 11,
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  }
}

function secondaryButtonStyle(color: string): React.CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    background: 'var(--bg-deep)',
    border: '1px solid var(--glass-border)',
    color,
    padding: '6px 9px',
    borderRadius: 'var(--radius-sm)',
    cursor: 'pointer',
    fontSize: 9,
    fontFamily: 'var(--font-mono)',
  }
}

function toolbarButtonStyle(disabled: boolean): React.CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    background: disabled ? 'rgba(236,230,218,0.03)' : 'var(--bg-deep)',
    border: '1px solid var(--glass-border)',
    color: disabled ? 'var(--text-tertiary)' : 'var(--text-secondary)',
    padding: '5px 8px',
    borderRadius: 'var(--radius-sm)',
    cursor: disabled ? 'default' : 'pointer',
    fontSize: 9,
    fontFamily: 'var(--font-mono)',
  }
}
