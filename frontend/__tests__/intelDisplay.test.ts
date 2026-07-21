import { describe, expect, test } from 'vitest'
import type { EventClusterResult, IntelItem, WarningIndicatorResult } from '../src/types'
import { buildItemAnalysisContext, itemConfidenceLevel, itemDisposition, sourceCount } from '../src/utils/intelDisplay'

const baseItem: IntelItem = {
  id: 'i1',
  title: 'Test item',
  summary: 'Summary',
  layer: 'military',
  location: { lat: 0, lng: 0 },
  location_name: 'Taiwan Province',
  country: '中国台湾省',
  confidence: 0.8,
  verdict: 'uncertain',
  bayesian_trace: [],
  evidence_count: 1,
  sources: ['Reuters', 'BBC'],
  source_system: 'Reuters',
  captured_at: '2026-06-01T00:00:00Z',
  url: 'https://example.com',
}

describe('intelDisplay', () => {
  test('derives OSINT confidence level from independent sources', () => {
    expect(sourceCount(baseItem)).toBe(2)
    expect(itemConfidenceLevel(baseItem).level).toBe('L2')
  })

  test('maps event and warning analysis context back to item ids', () => {
    const events: EventClusterResult = {
      scope: {},
      generated_at: '',
      total_items: 1,
      total_clusters: 1,
      unclustered_count: 0,
      clusters: [{
        id: 'EV01',
        title: 'Military deployment reported',
        summary: '',
        start_date: '2026-06-01',
        end_date: '2026-06-01',
        countries: ['中国台湾省'],
        layers: ['military'],
        item_count: 1,
        source_count: 2,
        confidence: { level: 'L2', label: '高可信', rationale: '', independent_source_count: 2, evidence_count: 1, evidence_ids: ['E01'] },
        verification_status: '双源支撑',
        key_terms: [],
        claims: [],
        evidence: [{ id: 'E01', item_id: 'i1', title: 'Test item', summary: '', source: 'Reuters', sources: ['Reuters', 'BBC'], date: '', layer: 'military', country: '中国台湾省', confidence: 0.8, confidence_level: 'L2', confidence_label: '高可信', url: '', verification: '', independent_source_count: 2 }],
      }],
    }
    const warnings: WarningIndicatorResult = {
      scope: {},
      generated_at: '',
      total_items: 1,
      overall_level: 'high',
      active_indicator_count: 1,
      methodology: '',
      indicators: [{
        id: 'W01',
        title: 'High impact warning',
        severity: 'high',
        status: 'triggered',
        confidence: { level: 'L2', label: '高可信', rationale: '', independent_source_count: 2, evidence_count: 1, evidence_ids: ['E01'] },
        trigger: '',
        rationale: '',
        countries: ['中国台湾省'],
        layers: ['military'],
        related_event_ids: ['EV01'],
        evidence_ids: ['E01'],
        next_steps: [],
        review_window: '12h',
      }],
      collection_requirements: [],
    }

    const context = buildItemAnalysisContext(events, warnings)

    expect(context.i1.eventId).toBe('EV01')
    expect(context.i1.eventConfidenceLevel).toBe('L2')
    expect(context.i1.warningSeverity).toBe('high')
  })

  test('derives analyst disposition from warning and corroboration state', () => {
    expect(itemDisposition(baseItem).label).toBe('可入简报')

    expect(itemDisposition({ ...baseItem, sources: [], confidence: 0.5 }).label).toBe('需交叉验证')

    expect(itemDisposition(baseItem, { warningSeverity: 'high', warningTitle: 'High impact warning' }).label).toBe('优先处置')
  })
})
