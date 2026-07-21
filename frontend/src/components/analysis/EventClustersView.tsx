import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, LinkSimple, WarningCircle } from '@phosphor-icons/react'
import { fetchEventClusters } from '../../api'
import type { BriefEvidence, EventCluster, EventClusterResult, IntelLayer } from '../../types'
import { LAYER_META } from '../../types'
import { safeExternalUrl } from '../../utils/safeUrl'
import { isAbortError } from '../../utils/request'

interface Props {
  selectedDate: string
  startDate?: string
  endDate?: string
  activeLayers: IntelLayer[]
  selectedClusterId?: string
  focusItemId?: string
  onSelectCluster?: (cluster: EventCluster) => void
}

function confidenceColor(level: string) {
  if (level === 'L1') return 'var(--success)'
  if (level === 'L2') return 'var(--accent)'
  if (level === 'L3') return 'var(--warning)'
  return 'var(--danger)'
}

function EvidenceRef({ id, evidence }: { id: string; evidence?: BriefEvidence }) {
  if (!evidence) return null
  const evidenceUrl = safeExternalUrl(evidence.url)
  if (!evidenceUrl) return null
  return (
    <a
      href={evidenceUrl}
      target="_blank"
      rel="noreferrer"
      title={evidence.title}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '2px 6px', borderRadius: 'var(--radius-sm)',
        background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
        color: 'var(--text-secondary)', fontSize: 9,
        fontFamily: 'var(--font-mono)', textDecoration: 'none',
      }}
    >
      <LinkSimple size={10} />
      {id}
    </a>
  )
}

export default function EventClustersView({
  selectedDate,
  startDate = '',
  endDate = '',
  activeLayers,
  selectedClusterId,
  focusItemId,
  onSelectCluster,
}: Props) {
  const [data, setData] = useState<EventClusterResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string>('')
  const requestGenerationRef = useRef(0)

  const date = startDate || endDate ? '' : selectedDate
  const layersKey = activeLayers.join(',')

  useEffect(() => {
    const requestGeneration = ++requestGenerationRef.current
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetchEventClusters({ date, startDate, endDate, layers: activeLayers }, controller.signal)
      .then(d => {
        if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) return
        setData(d)
        const initialCluster = selectedClusterId
          ? d.clusters.find(cluster => cluster.id === selectedClusterId)
          : focusItemId
            ? d.clusters.find(cluster => cluster.evidence.some(evidence => evidence.item_id === focusItemId))
            : d.clusters[0]
        setSelectedId(initialCluster?.id ?? '')
        if (initialCluster) onSelectCluster?.(initialCluster)
        setLoading(false)
      })
      .catch(e => {
        if (isAbortError(e) || requestGeneration !== requestGenerationRef.current) return
        setError(e instanceof Error ? e.message : '事件核查加载失败')
        setLoading(false)
      })
    return () => controller.abort()
  }, [date, startDate, endDate, layersKey, selectedClusterId, focusItemId])

  const activeSelectedId = selectedClusterId ?? selectedId
  const selected = useMemo(
    () => data?.clusters.find(cluster => cluster.id === activeSelectedId) ?? data?.clusters[0],
    [data, activeSelectedId],
  )

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

  if (!data || data.clusters.length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>当前范围暂无可聚类事件</div>
  }

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: 8,
      }}>
        <Metric label="样本数" value={data.total_items} />
        <Metric label="事件簇" value={data.total_clusters} />
        <Metric label="单条线索" value={data.unclustered_count} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
        <div style={{ display: 'grid', gap: 6, alignContent: 'start' }}>
          {data.clusters.slice(0, 20).map((cluster, i) => (
            <ClusterRow
              key={cluster.id}
              cluster={cluster}
              active={cluster.id === selected?.id}
              index={i}
              onClick={() => {
                setSelectedId(cluster.id)
                onSelectCluster?.(cluster)
              }}
            />
          ))}
        </div>
        {selected && <ClusterDetail cluster={selected} />}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={{
      padding: '9px 11px', background: 'var(--bg-deep)',
      border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-md)',
    }}>
      <div style={{ fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 16, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>{value}</div>
    </div>
  )
}

function ClusterRow({ cluster, active, index, onClick }: { cluster: EventCluster; active: boolean; index: number; onClick: () => void }) {
  const color = confidenceColor(cluster.confidence.level)
  return (
    <motion.button
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.02 }}
      onClick={onClick}
      style={{
        textAlign: 'left', cursor: 'pointer',
        padding: '9px 10px', borderRadius: 'var(--radius-md)',
        background: active ? `${color}10` : 'var(--bg-deep)',
        border: active ? `1px solid ${color}35` : '1px solid var(--glass-border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
        <span style={{ fontSize: 9, color, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{cluster.id}</span>
        <span style={{ fontSize: 8, color, fontFamily: 'var(--font-mono)' }}>{cluster.confidence.level}</span>
        <span style={{ marginLeft: 'auto', fontSize: 8, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          {cluster.item_count}条/{cluster.source_count}源
        </span>
      </div>
      <div style={{
        fontSize: 10, color: 'var(--text-primary)', lineHeight: 1.45,
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {cluster.title}
      </div>
    </motion.button>
  )
}

function ClusterDetail({ cluster }: { cluster: EventCluster }) {
  const evidenceById = new Map<string, BriefEvidence>()
  for (const evidence of cluster.evidence) evidenceById.set(evidence.id, evidence)
  const color = confidenceColor(cluster.confidence.level)

  return (
    <div style={{
      padding: '12px 14px', background: 'rgba(32,36,40,0.72)',
      border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-md)',
      minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
        {cluster.confidence.level === 'L1' || cluster.confidence.level === 'L2'
          ? <CheckCircle size={16} weight="duotone" color={color} style={{ flexShrink: 0, marginTop: 1 }} />
          : <WarningCircle size={16} weight="duotone" color={color} style={{ flexShrink: 0, marginTop: 1 }} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 5 }}>{cluster.title}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            <Badge color={color} text={`${cluster.confidence.level} ${cluster.confidence.label}`} />
            <Badge color={color} text={cluster.verification_status} />
            <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {cluster.start_date || '未知日期'}{cluster.end_date && cluster.end_date !== cluster.start_date ? ` → ${cluster.end_date}` : ''}
            </span>
          </div>
        </div>
      </div>

      <div style={{ fontSize: 10, lineHeight: 1.6, color: 'var(--text-secondary)', marginBottom: 10 }}>
        {cluster.summary}
      </div>

      <MetaBlock cluster={cluster} />

      <SectionTitle title="可验证主张" />
      <div style={{ display: 'grid', gap: 6, marginBottom: 12 }}>
        {cluster.claims.map(claim => (
          <div key={claim.id} style={{
            padding: '8px 10px', background: 'var(--bg-deep)',
            border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-sm)',
          }}>
            <div style={{ fontSize: 10, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 5 }}>{claim.claim}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              <Badge color={confidenceColor(claim.confidence.level)} text={`${claim.confidence.level} ${claim.verification_status}`} />
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {claim.support_count}条支撑 · {claim.source_count}源
              </span>
              {claim.evidence_ids.map(id => <EvidenceRef key={id} id={id} evidence={evidenceById.get(id)} />)}
            </div>
          </div>
        ))}
      </div>

      <SectionTitle title="证据" />
      <div style={{ display: 'grid', gap: 5 }}>
        {cluster.evidence.map(evidence => {
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
                display: 'grid', gridTemplateColumns: '38px 1fr auto', gap: 7,
                padding: '7px 9px', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-deep)', border: '1px solid var(--glass-border)',
                textDecoration: 'none',
              }}
            >
              <span style={{ fontSize: 9, color: meta?.color ?? 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{evidence.id}</span>
              <span style={{ minWidth: 0 }}>
                <span style={{ display: 'block', fontSize: 10, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {evidence.title}
                </span>
                <span style={{ display: 'block', fontSize: 8, color: 'var(--text-tertiary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {evidence.source} · {evidence.country || '未知地区'}
                </span>
              </span>
              <span style={{ fontSize: 8, color: confidenceColor(evidence.confidence_level), fontFamily: 'var(--font-mono)' }}>
                {evidence.confidence_level}
              </span>
            </a>
          )
        })}
      </div>
    </div>
  )
}

function MetaBlock({ cluster }: { cluster: EventCluster }) {
  return (
    <div style={{ display: 'grid', gap: 5, marginBottom: 12 }}>
      <MetaLine label="地区" value={cluster.countries.join('、') || '未知'} />
      <MetaLine label="图层" value={cluster.layers.map(layer => LAYER_META[layer as IntelLayer]?.label ?? layer).join('、')} />
      <MetaLine label="关键词" value={cluster.key_terms.join('、') || '无'} />
    </div>
  )
}

function MetaLine({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 8, fontSize: 9, lineHeight: 1.5 }}>
      <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{label}</span>
      <span style={{ color: 'var(--text-secondary)' }}>{value}</span>
    </div>
  )
}

function Badge({ color, text }: { color: string; text: string }) {
  return (
    <span style={{
      fontSize: 8, color, fontFamily: 'var(--font-mono)', fontWeight: 700,
      padding: '2px 6px', background: `${color}12`, border: `1px solid ${color}25`,
      borderRadius: 'var(--radius-sm)',
    }}>
      {text}
    </span>
  )
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
      {title}
    </div>
  )
}
