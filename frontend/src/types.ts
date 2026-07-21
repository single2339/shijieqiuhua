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
  page: number
  page_size: number
  has_more: boolean
  available_dates: string[]
  updated_at: string
}

// ── AI Q&A ──
export interface AskRequest {
  question: string
  start_date?: string
  end_date?: string
  layer?: string
  skills?: string[]
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
export type BriefMaterialType = 'item' | 'event' | 'judgment' | 'warning'
export type ReportDraftStatus = 'draft' | 'review' | 'published'

export interface BriefWorkspaceMaterial {
  id: string
  type: BriefMaterialType
  title: string
  summary?: string
  source?: string
  sources?: string[]
  date?: string
  layer?: string
  country?: string
  confidence_level?: string
  url?: string
  origin?: string
}

export interface BriefWorkspace {
  materials: BriefWorkspaceMaterial[]
  updated_at: string
}

export interface BriefReportHistoryEntry {
  id: string
  status: ReportDraftStatus
  saved_at: string
  report: SituationReport
  materials: BriefWorkspaceMaterial[]
}

export interface ReportRequest {
  topic?: string
  country?: string
  days?: number
  layer?: string
  detail_level?: string
  skills?: string[]
  item_ids?: string[]
  event_ids?: string[]
  warning_ids?: string[]
  source_materials?: BriefWorkspaceMaterial[]
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
  shared_events: number
  confirmed_events: number
  high_confidence_events: number
  shared_event_ids: string[]
  shared_event_titles: string[]
  verification_summary: string
}

export interface CorroborationResult {
  sources: string[]
  matrix: number[][]
  top_pairs: SourcePairOverlap[]
  event_count: number
  claim_count: number
  methodology: string
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

export interface BriefEvidence {
  id: string
  item_id: string
  title: string
  summary: string
  source: string
  sources: string[]
  date: string
  layer: string
  country: string
  confidence: number
  confidence_level: string
  confidence_label: string
  url: string
  verification: string
  independent_source_count: number
}

export interface ConfidenceAssessment {
  level: string
  label: string
  rationale: string
  independent_source_count: number
  evidence_count: number
  evidence_ids: string[]
}

export interface KeyJudgment {
  id: string
  judgment: string
  confidence_level: string
  confidence_score: number
  impact: string
  time_sensitivity: string
  support_count: number
  evidence_ids: string[]
  uncertainties: string[]
  confidence_assessment?: ConfidenceAssessment
}

export interface IntelligenceStatement {
  id: string
  statement: string
  confidence: ConfidenceAssessment
  evidence_ids: string[]
  note: string
}

export interface CoreFinding {
  id: string
  finding: string
  fact_basis: string
  assessment: string
  confidence: ConfidenceAssessment
  evidence_ids: string[]
  implications: string[]
}

export interface AlternativeExplanation {
  id: string
  explanation: string
  indicators: string[]
  related_evidence_ids: string[]
  confidence_level: string
}

export interface PendingVerification {
  id: string
  question: string
  priority: string
  rationale: string
  related_evidence_ids: string[]
}

export interface EventClaim {
  id: string
  claim: string
  confidence: ConfidenceAssessment
  support_count: number
  source_count: number
  evidence_ids: string[]
  verification_status: string
}

export interface EventCluster {
  id: string
  title: string
  summary: string
  start_date: string
  end_date: string
  countries: string[]
  layers: string[]
  item_count: number
  source_count: number
  confidence: ConfidenceAssessment
  verification_status: string
  key_terms: string[]
  claims: EventClaim[]
  evidence: BriefEvidence[]
}

export interface EventClusterResult {
  scope: Record<string, unknown>
  generated_at: string
  total_items: number
  total_clusters: number
  unclustered_count: number
  clusters: EventCluster[]
}

export interface BriefIssue {
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  related_evidence_ids: string[]
}

export interface CollectionTask {
  priority: string
  task: string
  rationale: string
  query: string
}

export interface WarningIndicator {
  id: string
  title: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: string
  confidence: ConfidenceAssessment
  trigger: string
  rationale: string
  countries: string[]
  layers: string[]
  related_event_ids: string[]
  evidence_ids: string[]
  next_steps: string[]
  review_window: string
}

export interface WarningIndicatorResult {
  scope: Record<string, unknown>
  generated_at: string
  total_items: number
  overall_level: 'normal' | 'watch' | 'high' | 'critical'
  active_indicator_count: number
  methodology: string
  indicators: WarningIndicator[]
  collection_requirements: CollectionTask[]
}

export interface SituationBriefResult {
  scope: Record<string, unknown>
  generated_at: string
  summary: string
  total_items: number
  methodology: string
  intelligence_level: ConfidenceAssessment | null
  source_count: number
  core_findings: CoreFinding[]
  confirmed_facts: IntelligenceStatement[]
  assessments: IntelligenceStatement[]
  alternative_explanations: AlternativeExplanation[]
  pending_verification: PendingVerification[]
  key_judgments: KeyJudgment[]
  evidence: BriefEvidence[]
  contradictions: BriefIssue[]
  collection_gaps: BriefIssue[]
  recommended_tasks: CollectionTask[]
  recommended_next_steps: CollectionTask[]
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
  investigation_type?: InvestigationPlaybook
  target?: string
  purpose?: string
  authorized?: boolean
  verification_depth?: 'standard' | 'deep'
  skills?: string[]
  request_id?: string
}

export type InvestigationPlaybook = 'general' | 'person' | 'website' | 'image' | 'identity' | 'event' | 'threat'
export type SuperAnalysisConfidenceLevel = 'L1' | 'L2' | 'L3' | 'L4' | 'L5'

export interface BayesianIntelItem {
  document_id?: string
  title: string
  source: string
  date: string
  layer: string
  quality_score: number
  independent_source_count: number
  source_class: string
  content_snippet: string
  source_url?: string
}

export interface HypothesisEvidenceAssessment {
  evidence_id: string
  source: string
  relation: 'support' | 'contradict' | 'neutral'
  strength: 'weak' | 'moderate' | 'strong'
  likelihood_ratio: number
  posterior_probability: number
  rationale: string
}

export interface HypothesisAssessment {
  hypothesis: string
  prior_probability: number
  posterior_probability: number
  verdict: 'verified' | 'refuted' | 'uncertain'
  confidence_level: SuperAnalysisConfidenceLevel
  independent_source_count: number
  evidence: HypothesisEvidenceAssessment[]
}

export interface WebResult {
  title: string
  snippet: string
  url: string
}

export interface InvestigationPlan {
  playbook: InvestigationPlaybook
  target: string
  collection_steps: string[]
  verification_steps: string[]
}

export interface InvestigationEvidence {
  id: string
  kind: string
  title: string
  source: string
  provenance: string
  collected_at: string
  verification_status: 'collected' | 'captured' | 'corroborated' | 'failed' | 'unverified'
  summary: string
  source_url: string
  content_sha256: string
  data: Record<string, unknown>
}

export interface InvestigationRelationshipNode {
  id: string
  label: string
  type: string
}

export interface InvestigationRelationshipEdge {
  source: string
  target: string
  relation: string
  evidence_ids: string[]
}

export interface InvestigationTimelineEntry {
  date: string
  evidence_ids: string[]
  summary: string
}

export interface InvestigationAnalystReview {
  status: 'pending' | 'approved' | 'needs_follow_up' | 'rejected'
  reviewer_id: number | null
  reviewed_at: string
  notes: string
}

export interface InvestigationReviewRequest {
  status: 'approved' | 'needs_follow_up' | 'rejected'
  notes: string
}

export interface InvestigationResult {
  playbook: InvestigationPlaybook
  scope: Record<string, unknown>
  plan: InvestigationPlan
  evidence: InvestigationEvidence[]
  relationship_graph: {
    nodes: InvestigationRelationshipNode[]
    edges: InvestigationRelationshipEdge[]
  }
  timeline: InvestigationTimelineEntry[]
  pending_verification: PendingVerification[]
  alternative_explanations: AlternativeExplanation[]
  recommended_next_steps: CollectionTask[]
  analyst_review: InvestigationAnalystReview
  errors: string[]
}

export interface SuperAnalysisResponse {
  question: string
  analysis: string
  relevant_items: BayesianIntelItem[]
  web_results: WebResult[]
  hypothesis_assessment: HypothesisAssessment | null
  investigation?: InvestigationResult | null
  collection_status: 'complete' | 'empty' | 'partial' | 'unavailable'
  provider_statuses: Record<string, 'success' | 'empty' | 'error' | 'disabled'>
  degraded: boolean
  analysis_status: 'complete' | 'unavailable' | 'error'
  errors: string[]
  model: string
  request_id: string
}

// ── Auth & User ──

export interface UserInfo {
  id: number
  username: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface LoginResponse {
  user: UserInfo
  access_token: string
  refresh_token: string
}

// ── Admin ──

export interface AdminUserDetail {
  id: number
  username: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
  last_login_at: string | null
  action_count: number
  recent_actions?: Array<{ action_type: string; details_json: string; ip_address: string; created_at: string }>
}

export interface InviteCodeInfo {
  id: number
  code: string
  created_by: string | null
  max_uses: number
  current_uses: number
  is_active: boolean
  created_at: string
  expires_at: string | null
}

export interface AdminStats {
  total_users: number
  active_7d: number
  active_30d: number
  today_logins: number
  today_actions: number
  daily_logins: Array<{ date: string; count: number }>
  daily_actions: Array<{ date: string; action_type: string; count: number }>
  top_users: Array<{ username: string; action_count: number }>
  invite_code_usage: { total: number; used: number }
}

export const LAYER_META: Record<IntelLayer, { label: string; color: string }> = {
  nature:      { label: '自然生态', color: '#6f9f7a' },
  economy:     { label: '经济产业', color: '#7894a3' },
  finance:     { label: '金融',     color: '#c8a45d' },
  politics:    { label: '政治外交', color: '#b88a5a' },
  military:    { label: '军事',     color: '#bf6f63' },
  aviation:    { label: '民航交通', color: '#7c8c95' },
  technology:  { label: '科技',     color: '#8fa3a7' },
  society:     { label: '社会民生', color: '#b47670' },
  energy:      { label: '能源资源', color: '#bd835f' },
  agriculture: { label: '农业食品', color: '#7e986b' },
  health:      { label: '公共卫生', color: '#6ea6a0' },
  cyber:       { label: '网络空间', color: '#7284a3' },
}
