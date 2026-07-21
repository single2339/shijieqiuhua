import type { BriefWorkspaceMaterial, EventClusterResult, IntelItem, WarningIndicatorResult } from '../types'

export interface ItemAnalysisContext {
  eventId?: string
  eventTitle?: string
  eventConfidenceLevel?: string
  eventConfidenceLabel?: string
  eventVerificationStatus?: string
  eventSourceCount?: number
  warningId?: string
  warningTitle?: string
  warningSeverity?: 'low' | 'medium' | 'high' | 'critical'
  warningStatus?: string
}

export interface IntelligenceDisposition {
  label: string
  rationale: string
  priority: 'high' | 'medium' | 'low'
  tone: string
}

export function sourceCount(item: IntelItem): number {
  return new Set([...(item.sources ?? []), item.source_system].filter(Boolean)).size
}

export function itemConfidenceLevel(item: IntelItem): { level: string; label: string; rationale: string } {
  const sources = sourceCount(item)
  if (sources >= 3) {
    return { level: 'L1', label: '确认', rationale: '至少 3 个独立来源支撑。' }
  }
  if (sources === 2) {
    return { level: 'L2', label: '高可信', rationale: '2 个独立来源支撑。' }
  }
  if (item.confidence >= 0.6) {
    return { level: 'L3', label: '中可信', rationale: '单一来源且基础评分较高。' }
  }
  return { level: 'L4', label: '推测', rationale: '证据不足，需补充独立来源。' }
}

export function confidenceColor(level: string): string {
  if (level === 'L1') return 'var(--success)'
  if (level === 'L2') return 'var(--accent)'
  if (level === 'L3') return 'var(--warning)'
  return 'var(--danger)'
}

export function warningColor(severity?: string): string {
  if (severity === 'critical') return '#f87171'
  if (severity === 'high') return '#fb923c'
  if (severity === 'medium') return '#fbbf24'
  if (severity === 'low') return '#a3a3a3'
  return 'var(--text-tertiary)'
}

export function warningLabel(severity?: string): string {
  if (severity === 'critical') return '严重预警'
  if (severity === 'high') return '高预警'
  if (severity === 'medium') return '观察'
  if (severity === 'low') return '低'
  return ''
}

export function itemDisposition(item: IntelItem, context?: ItemAnalysisContext): IntelligenceDisposition {
  const level = context?.eventConfidenceLevel ?? itemConfidenceLevel(item).level
  const sources = context?.eventSourceCount ?? sourceCount(item)

  if (context?.warningSeverity === 'critical' || context?.warningSeverity === 'high') {
    return {
      label: '优先处置',
      rationale: '已触发高等级预警，应优先进入人工复核和态势跟踪。',
      priority: 'high',
      tone: warningColor(context.warningSeverity),
    }
  }

  if ((level === 'L1' || level === 'L2') && sources >= 2) {
    return {
      label: '可入简报',
      rationale: '具备多源支撑，可纳入简报，但仍需保留来源链路。',
      priority: 'medium',
      tone: confidenceColor(level),
    }
  }

  if (level === 'L3' || sources < 2) {
    return {
      label: '需交叉验证',
      rationale: '当前仍以单源或有限证据为主，应补充独立来源。',
      priority: 'medium',
      tone: 'var(--warning)',
    }
  }

  return {
    label: '仅作线索',
    rationale: '证据不足或基础评分偏低，不宜直接进入判断结论。',
    priority: 'low',
    tone: 'var(--danger)',
  }
}

export function buildItemAnalysisContext(
  events?: EventClusterResult | null,
  warnings?: WarningIndicatorResult | null,
): Record<string, ItemAnalysisContext> {
  const context: Record<string, ItemAnalysisContext> = {}
  const warningByEvent = new Map<string, WarningIndicatorResult['indicators'][number]>()

  for (const warning of warnings?.indicators ?? []) {
    for (const eventId of warning.related_event_ids) {
      const current = warningByEvent.get(eventId)
      if (!current || severityRank(warning.severity) > severityRank(current.severity)) {
        warningByEvent.set(eventId, warning)
      }
    }
  }

  for (const event of events?.clusters ?? []) {
    const warning = warningByEvent.get(event.id)
    for (const evidence of event.evidence) {
      if (!evidence.item_id) continue
      context[evidence.item_id] = {
        eventId: event.id,
        eventTitle: event.title,
        eventConfidenceLevel: event.confidence.level,
        eventConfidenceLabel: event.confidence.label,
        eventVerificationStatus: event.verification_status,
        eventSourceCount: event.source_count,
        warningId: warning?.id,
        warningTitle: warning?.title,
        warningSeverity: warning?.severity,
        warningStatus: warning?.status,
      }
    }
  }

  return context
}

function severityRank(severity: string): number {
  return { critical: 4, high: 3, medium: 2, low: 1 }[severity] ?? 0
}

export function itemToBriefMaterial(item: IntelItem, origin: string): BriefWorkspaceMaterial {
  const level = itemConfidenceLevel(item)
  return {
    id: item.id,
    type: 'item',
    title: item.title,
    summary: item.summary,
    source: item.source_system,
    sources: item.sources,
    date: item.captured_at?.slice(0, 10) || '',
    layer: item.layer,
    country: item.country,
    confidence_level: `${level.level} ${level.label}`,
    url: item.url,
    origin,
  }
}
