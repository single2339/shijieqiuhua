import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, LinkSimple, Target, WarningCircle } from '@phosphor-icons/react'
import { fetchSituationBrief } from '../../api'
import type {
  AlternativeExplanation,
  BriefEvidence,
  BriefWorkspaceMaterial,
  CollectionTask,
  ConfidenceAssessment,
  CoreFinding,
  IntelLayer,
  IntelligenceStatement,
  PendingVerification,
  SituationBriefResult,
} from '../../types'
import { LAYER_META } from '../../types'
import { safeExternalUrl } from '../../utils/safeUrl'
import { isAbortError } from '../../utils/request'

interface Props {
  selectedDate: string
  startDate?: string
  endDate?: string
  activeLayers: IntelLayer[]
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#f87171',
  high: '#fb923c',
  medium: '#fbbf24',
  low: '#a3a3a3',
}

function confidenceColor(level: string) {
  if (level === 'L1') return 'var(--success)'
  if (level === 'L2') return 'var(--accent)'
  if (level === 'L3') return 'var(--warning)'
  if (level === '高') return 'var(--success)'
  if (level === '中') return 'var(--warning)'
  return 'var(--danger)'
}

function ConfidenceBadge({ confidence }: { confidence?: ConfidenceAssessment | null }) {
  if (!confidence) return null
  const color = confidenceColor(confidence.level)
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '2px 7px', borderRadius: 'var(--radius-sm)',
      background: `${color}12`, border: `1px solid ${color}30`,
      color, fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
    }}>
      {confidence.level} {confidence.label}
      <span style={{ color: 'var(--text-tertiary)', fontWeight: 500 }}>
        {confidence.independent_source_count}源
      </span>
    </span>
  )
}

function EvidenceRef({ id, evidence }: { id: string; evidence?: BriefEvidence }) {
  if (!evidence) return null
  const evidenceUrl = safeExternalUrl(evidence.url)
  if (!evidenceUrl) return null
  const meta = LAYER_META[evidence.layer as IntelLayer]
  return (
    <a
      href={evidenceUrl}
      target="_blank"
      rel="noreferrer"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '2px 6px', borderRadius: 'var(--radius-sm)',
        background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
        color: meta?.color ?? 'var(--text-secondary)', fontSize: 9,
        fontFamily: 'var(--font-mono)', textDecoration: 'none',
      }}
      title={evidence.title}
    >
      <LinkSimple size={10} />
      {id}
    </a>
  )
}

export default function SituationBriefView({ selectedDate, startDate = '', endDate = '', activeLayers, onAddToBrief }: Props) {
  const [data, setData] = useState<SituationBriefResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const requestGenerationRef = useRef(0)

  const date = startDate || endDate ? '' : selectedDate
  const layersKey = activeLayers.join(',')

  useEffect(() => {
    const requestGeneration = ++requestGenerationRef.current
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetchSituationBrief({ date, startDate, endDate, layers: activeLayers }, controller.signal)
      .then(d => {
        if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) return
        setData(d)
        setLoading(false)
      })
      .catch(e => {
        if (isAbortError(e) || requestGeneration !== requestGenerationRef.current) return
        setError(e instanceof Error ? e.message : '态势研判加载失败')
        setLoading(false)
      })
    return () => controller.abort()
  }, [date, startDate, endDate, layersKey])

  const evidenceById = useMemo(() => {
    const map = new Map<string, BriefEvidence>()
    for (const evidence of data?.evidence ?? []) map.set(evidence.id, evidence)
    return map
  }, [data])

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          style={{
            width: 20, height: 20, borderRadius: '50%', margin: '0 auto',
            border: '2px solid var(--border-subtle)', borderTopColor: 'var(--accent)',
          }}
        />
      </div>
    )
  }

  if (error) {
    return <div style={{ color: 'var(--danger)', fontSize: 11, textAlign: 'center', padding: 20 }}>{error}</div>
  }

  if (!data) return null

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <Panel>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            情报摘要
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {data.total_items} 条 · {data.source_count} 源 · {date || `${startDate || '起始'} → ${endDate || '现在'}`}
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          <ConfidenceBadge confidence={data.intelligence_level} />
          <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {data.methodology}
          </span>
        </div>
        <div style={{ fontSize: 11, lineHeight: 1.7, color: 'var(--text-secondary)' }}>{data.summary}</div>
      </Panel>

      <section>
        <SectionTitle title="核心发现" />
        <div style={{ display: 'grid', gap: 8 }}>
          {data.core_findings.length === 0 && <EmptyNote text="当前范围暂无可形成核心发现的证据。" />}
          {data.core_findings.map((finding, i) => (
            <CoreFindingCard
              key={finding.id}
              finding={finding}
              evidenceById={evidenceById}
              index={i}
              onAddToBrief={onAddToBrief}
            />
          ))}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
        <section>
          <SectionTitle title="确认事实" />
          <div style={{ display: 'grid', gap: 6 }}>
            {data.confirmed_facts.map(fact => (
              <StatementCard key={fact.id} statement={fact} evidenceById={evidenceById} onAddToBrief={onAddToBrief} />
            ))}
          </div>
        </section>

        <section>
          <SectionTitle title="分析判断" />
          <div style={{ display: 'grid', gap: 6 }}>
            {data.assessments.map(assessment => (
              <StatementCard key={assessment.id} statement={assessment} evidenceById={evidenceById} onAddToBrief={onAddToBrief} />
            ))}
          </div>
        </section>
      </div>

      <section>
        <SectionTitle title="证据链" />
        <div style={{ display: 'grid', gap: 6 }}>
          {data.evidence.slice(0, 10).map(evidence => {
            const meta = LAYER_META[evidence.layer as IntelLayer]
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
                  padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
                  textDecoration: 'none',
                }}
              >
                <span style={{ fontSize: 10, color: meta?.color ?? 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                  {evidence.id}
                </span>
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 11, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {evidence.title}
                  </span>
                  <span style={{ display: 'block', fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {evidence.source} · {evidence.country || '未知地区'} · {evidence.verification}
                  </span>
                </span>
                <span style={{ fontSize: 9, color: confidenceColor(evidence.confidence_level), fontFamily: 'var(--font-mono)' }}>
                  {evidence.confidence_level}
                </span>
              </a>
            )
          })}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
        <section>
          <SectionTitle title="替代解释" />
          <div style={{ display: 'grid', gap: 6 }}>
            {data.alternative_explanations.length === 0 && <EmptyNote text="暂无明显替代解释，但仍需持续寻找反证。" />}
            {data.alternative_explanations.map(item => (
              <AlternativeCard key={item.id} item={item} evidenceById={evidenceById} />
            ))}
          </div>
        </section>

        <section>
          <SectionTitle title="待确认与下一步" />
          <div style={{ display: 'grid', gap: 6 }}>
            {data.pending_verification.length === 0 && <EmptyNote text="当前范围未发现高优先级验证缺口。" />}
            {data.pending_verification.map(item => (
              <VerificationCard key={item.id} item={item} evidenceById={evidenceById} />
            ))}
            {(data.recommended_next_steps.length ? data.recommended_next_steps : data.recommended_tasks).map((task, i) => (
              <TaskCard key={`${task.task}-${i}`} task={task} />
            ))}
          </div>
        </section>
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

function Panel({ children }: { children: ReactNode }) {
  return (
    <div style={{
      padding: '12px 14px', background: 'var(--bg-deep)',
      border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-md)',
    }}>
      {children}
    </div>
  )
}

function CoreFindingCard({
  finding,
  evidenceById,
  index,
  onAddToBrief,
}: {
  finding: CoreFinding
  evidenceById: Map<string, BriefEvidence>
  index: number
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      style={{
        padding: '12px 14px', borderRadius: 'var(--radius-md)',
        border: '1px solid var(--glass-border)', background: 'rgba(32,36,40,0.72)',
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <CheckCircle size={16} weight="duotone" color={confidenceColor(finding.confidence.level)} style={{ marginTop: 1, flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 6 }}>
            <ConfidenceBadge confidence={finding.confidence} />
            {finding.evidence_ids.map(id => <EvidenceRef key={id} id={id} evidence={evidenceById.get(id)} />)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.55, marginBottom: 6 }}>
            {finding.finding}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.55 }}>{finding.fact_basis}</div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.55, marginTop: 4 }}>{finding.assessment}</div>
          {onAddToBrief && (
            <MiniAction label="将判断加入简报" onClick={() => onAddToBrief(findingToMaterial(finding, evidenceById))} />
          )}
        </div>
      </div>
    </motion.div>
  )
}

function StatementCard({
  statement,
  evidenceById,
  onAddToBrief,
}: {
  statement: IntelligenceStatement
  evidenceById: Map<string, BriefEvidence>
  onAddToBrief?: (material: BriefWorkspaceMaterial) => void
}) {
  return (
    <Panel>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <ConfidenceBadge confidence={statement.confidence} />
        {statement.evidence_ids.slice(0, 4).map(id => <EvidenceRef key={id} id={id} evidence={evidenceById.get(id)} />)}
      </div>
      <div style={{ fontSize: 11, lineHeight: 1.6, color: 'var(--text-primary)' }}>{statement.statement}</div>
      {statement.note && <div style={{ fontSize: 9, lineHeight: 1.5, color: 'var(--text-tertiary)', marginTop: 5 }}>{statement.note}</div>}
      {onAddToBrief && (
        <MiniAction label="将判断加入简报" onClick={() => onAddToBrief(statementToMaterial(statement, evidenceById))} />
      )}
    </Panel>
  )
}

function MiniAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        marginTop: 8,
        display: 'inline-flex',
        alignItems: 'center',
        padding: '5px 8px',
        border: '1px solid rgba(200,164,93,0.24)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--accent-dim)',
        color: 'var(--accent)',
        cursor: 'pointer',
        fontSize: 9,
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
      }}
    >
      {label}
    </button>
  )
}

function evidenceMeta(ids: string[], evidenceById: Map<string, BriefEvidence>) {
  const evidence = ids.map(id => evidenceById.get(id)).filter((item): item is BriefEvidence => Boolean(item))
  const sources = [...new Set(evidence.flatMap(item => [item.source, ...(item.sources ?? [])]).filter(Boolean))]
  return {
    source: sources[0] || '',
    sources,
    date: evidence[0]?.date || '',
    layer: [...new Set(evidence.map(item => item.layer).filter(Boolean))].join(','),
    country: [...new Set(evidence.map(item => item.country).filter(Boolean))].join(','),
    url: evidence[0]?.url || '',
  }
}

function findingToMaterial(finding: CoreFinding, evidenceById: Map<string, BriefEvidence>): BriefWorkspaceMaterial {
  return {
    id: finding.id,
    type: 'judgment',
    title: finding.finding,
    summary: [finding.fact_basis, finding.assessment].filter(Boolean).join('\n'),
    confidence_level: `${finding.confidence.level} ${finding.confidence.label}`,
    origin: '态势研判',
    ...evidenceMeta(finding.evidence_ids, evidenceById),
  }
}

function statementToMaterial(statement: IntelligenceStatement, evidenceById: Map<string, BriefEvidence>): BriefWorkspaceMaterial {
  return {
    id: statement.id,
    type: 'judgment',
    title: statement.statement,
    summary: statement.note,
    confidence_level: `${statement.confidence.level} ${statement.confidence.label}`,
    origin: '态势研判',
    ...evidenceMeta(statement.evidence_ids, evidenceById),
  }
}

function AlternativeCard({ item, evidenceById }: { item: AlternativeExplanation; evidenceById: Map<string, BriefEvidence> }) {
  return (
    <IssueShell color={confidenceColor(item.confidence_level)}>
      <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{item.explanation}</div>
      {item.indicators.length > 0 && (
        <div style={{ fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.5, marginTop: 4 }}>
          {item.indicators.join(' · ')}
        </div>
      )}
      <EvidenceList ids={item.related_evidence_ids} evidenceById={evidenceById} />
    </IssueShell>
  )
}

function VerificationCard({ item, evidenceById }: { item: PendingVerification; evidenceById: Map<string, BriefEvidence> }) {
  const color = item.priority === '高' ? 'var(--danger)' : 'var(--warning)'
  return (
    <IssueShell color={color}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 3 }}>
        <span style={{ fontSize: 8, color, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{item.priority}</span>
        <span style={{ fontSize: 10, color: 'var(--text-primary)', fontWeight: 700 }}>{item.question}</span>
      </div>
      <div style={{ fontSize: 9, lineHeight: 1.5, color: 'var(--text-tertiary)' }}>{item.rationale}</div>
      <EvidenceList ids={item.related_evidence_ids} evidenceById={evidenceById} />
    </IssueShell>
  )
}

function TaskCard({ task }: { task: CollectionTask }) {
  return (
    <div style={{
      padding: '8px 10px', borderRadius: 'var(--radius-sm)',
      background: 'var(--accent-dim)', border: '1px solid rgba(200,164,93,0.22)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <Target size={12} weight="duotone" color="var(--accent)" />
        <span style={{ fontSize: 10, color: 'var(--text-primary)', fontWeight: 700 }}>{task.task}</span>
        <span style={{ marginLeft: 'auto', fontSize: 8, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{task.priority}</span>
      </div>
      <div style={{ fontSize: 9, lineHeight: 1.5, color: 'var(--text-tertiary)' }}>{task.rationale}</div>
    </div>
  )
}

function EvidenceList({ ids, evidenceById }: { ids: string[]; evidenceById: Map<string, BriefEvidence> }) {
  if (ids.length === 0) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
      {ids.map(id => <EvidenceRef key={id} id={id} evidence={evidenceById.get(id)} />)}
    </div>
  )
}

function IssueShell({ color, children }: { color: string; children: ReactNode }) {
  return (
    <div style={{
      padding: '8px 10px', borderRadius: 'var(--radius-sm)',
      background: `${color}10`, border: `1px solid ${color}24`,
    }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
        <WarningCircle size={13} weight="duotone" color={color} style={{ marginTop: 1, flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
      </div>
    </div>
  )
}

function EmptyNote({ text }: { text: string }) {
  return (
    <div style={{ padding: '8px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-deep)', color: 'var(--text-tertiary)', fontSize: 10 }}>
      {text}
    </div>
  )
}
