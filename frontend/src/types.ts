export type IntelLayer = 'nature' | 'economy' | 'finance' | 'politics' | 'military' | 'aviation' | 'technology' | 'society' | 'energy' | 'agriculture' | 'health' | 'cyber'
export type Verdict = 'verified' | 'false' | 'uncertain'

export interface GeoPoint {
  lat: number
  lng: number
}

export interface IntelItem {
  id: string
  title: string
  summary: string
  layer: IntelLayer
  location: GeoPoint
  location_name: string
  country: string
  confidence: number
  verdict: Verdict
  bayesian_trace: number[]
  evidence_count: number
  sources: string[]
  source_system: string
  captured_at: string
  url: string
  bayesian_method?: string
  bayesian_prior_quality?: string
  bayesian_prior_class?: string
  bayesian_evidence_items?: BayesianEvidenceItem[]
}

export interface BayesianEvidenceItem {
  name: string
  quality: string
  lr: number
  dep_discount: number
  direction: string
}

export interface SourceInfo {
  name: string
  credibility: number
  document_count: number
  last_seen: string
}

export interface LayerSummary {
  layer: IntelLayer
  count: number
  avg_confidence: number
}

export interface DashboardData {
  intel_items: IntelItem[]
  sources: SourceInfo[]
  layers: LayerSummary[]
  total_items: number
  updated_at: string
}

// ── AI Q&A ──
export interface AskRequest {
  question: string
  start_date?: string
  end_date?: string
  layer?: string
}

export interface AskResponse {
  answer: string
  references: Array<{ title: string; source: string; date: string }>
  model: string
}

// ── Dashboard Stats ──
export interface TrendPoint {
  date: string
  count: number
}

export interface SourceMatrix {
  name: string
  credibility: number
  document_count: number
  layer_distribution: Record<string, number>
}

export interface DashboardStats {
  total_items: number
  total_sources: number
  by_layer: LayerSummary[]
  daily_trend: TrendPoint[]
  source_matrix: SourceMatrix[]
  geo_distribution: Array<{ country: string; count: number }>
  top_keywords: Array<{ word: string; count: number }>
}

// ── Situation Report ──
export interface ReportRequest {
  topic?: string
  country?: string
  days?: number
  layer?: string
  detail_level?: string
}

export interface ReportSection {
  heading: string
  body: string
}

export interface SituationReport {
  title: string
  generated_at: string
  summary: string
  sections: ReportSection[]
  item_count: number
  source_count: number
}

// ── Intelligence Analysis ──

export interface TimelinePoint {
  date: string
  count: number
  items: Array<{
    id: string
    title: string
    layer: string
    country: string
    confidence: number
    source_system: string
  }>
  layer_counts: Record<string, number>
}

export interface TimelineResult {
  points: TimelinePoint[]
  date_range: { start: string; end: string; days: number }
}

export interface EntityNode {
  id: string
  label: string
  type: 'person' | 'org' | 'location'
  count: number
}

export interface EntityEdge {
  source: string
  target: string
  weight: number
}

export interface EntityGraphResult {
  nodes: EntityNode[]
  edges: EntityEdge[]
}

export interface SourcePairOverlap {
  source_a: string
  source_b: string
  shared_topics: number
  total_a: number
  total_b: number
  agreement_score: number
}

export interface CorroborationResult {
  sources: string[]
  matrix: number[][]
  top_pairs: SourcePairOverlap[]
}

export interface AnomalyEvent {
  date: string
  layer: string
  country: string
  actual_count: number
  expected_count: number
  z_score: number
  severity: 'low' | 'medium' | 'high' | 'critical'
}

export interface AnomalyResult {
  anomalies: AnomalyEvent[]
  baseline: Record<string, { mean: number; std: number; days: number }>
}

export interface RegionRisk {
  country: string
  risk_score: number
  intel_density: number
  avg_confidence: number
  layer_breakdown: Record<string, number>
}

export interface RiskHeatmapResult {
  regions: RegionRisk[]
}

export interface CoverageGap {
  gap_type: 'region' | 'topic' | 'time' | 'cross_source'
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  affected_region: string
  affected_layer: string
  recommendation: string
}

export interface GapAnalysisResult {
  gaps: CoverageGap[]
  coverage_stats: Record<string, number>
}

export interface AnalysisInterpretRequest {
  analysis_type: string
  context: Record<string, unknown>
}

export interface AnalysisInterpretResponse {
  analysis_type: string
  interpretation: string
  generated_at: string
}

// ── Super Analysis ──

export interface SuperAnalysisRequest {
  question: string
  start_date?: string
  end_date?: string
}

export interface BayesianIntelItem {
  title: string
  source: string
  date: string
  layer: string
  confidence: number
  verdict: string
  prior_class: string
  prior_probability: number
  evidence_items: Array<{ name: string; quality: string; lr: number; direction: string }>
  bayesian_trace: number[]
  content_snippet: string
}

export interface SuperAnalysisResponse {
  question: string
  analysis: string
  relevant_items: BayesianIntelItem[]
  web_results: Array<{ title: string; snippet: string; url: string }>
  model: string
}

export const LAYER_META: Record<IntelLayer, { label: string; color: string }> = {
  nature:      { label: '自然生态', color: '#2ecc71' },
  economy:     { label: '经济产业', color: '#3498db' },
  finance:     { label: '金融',     color: '#f39c12' },
  politics:    { label: '政治外交', color: '#9b59b6' },
  military:    { label: '军事',     color: '#e74c3c' },
  aviation:    { label: '民航交通', color: '#607d8b' },
  technology:  { label: '科技',     color: '#ff4081' },
  society:     { label: '社会民生', color: '#e91e63' },
  energy:      { label: '能源资源', color: '#ff5722' },
  agriculture: { label: '农业食品', color: '#4caf50' },
  health:      { label: '公共卫生', color: '#00bcd4' },
  cyber:       { label: '网络空间', color: '#1a237e' },
}
