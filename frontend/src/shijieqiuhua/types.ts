export type QuestionDimension = 'half' | 'cards' | 'corners' | 'goals' | 'player' | 'risk'

export interface MatchQuestion {
  id: QuestionDimension
  label: string
  prompt: string
}

export interface FootballMatch {
  id: string
  league: string
  kickoffAt: string
  kickoffIso: string
  homeTeam: string
  awayTeam: string
  provider?: string
  provider_match_id?: string
  home_provider_id?: string
  away_provider_id?: string
  publicLean: string
  questions: MatchQuestion[]
}

export interface FixtureStatus {
  id: string
  league: string
  kickoff_at: string
  kickoff_iso?: string
  home_team: string
  away_team: string
  provider?: string
  provider_match_id?: string
  home_provider_id?: string
  away_provider_id?: string
  status: 'scheduled' | 'live' | 'finished'
  home_score: number | null
  away_score: number | null
}

export type OsintJobStatus = 'queued' | 'running' | 'needs_review' | 'completed' | 'failed'
export type OsintJobPhase = 'queued' | 'verify' | 'collect' | 'normalize' | 'score' | 'report' | 'done'

export interface FootballOsintJobRequest {
  home_team: string
  away_team: string
  kickoff_at?: string
  competition?: string
  venue?: string
  provider?: string
  provider_match_id?: string
  home_provider_id?: string
  away_provider_id?: string
  home_aliases?: string[]
  away_aliases?: string[]
  locale?: string
  question?: string
  user_supplied?: {
    injuries?: Record<string, unknown>[]
    lineups?: Record<string, unknown>[]
    notes?: string[]
  }
}

export interface FootballQuestionAnswer {
  related: boolean
  analysis_started: boolean
  answer: string
  judgment: string
  reasons: string[]
  confidence_level: 'L1' | 'L2' | 'L3' | 'L4'
}

export interface OsintMatchProfile {
  competition_type: string
  time_to_kickoff_hours?: number | null
  data_density: string
  factor_pack: string
}

export interface OsintMatch {
  home_team: string
  away_team: string
  kickoff_at?: string
  competition?: string
  venue?: string
  profile: OsintMatchProfile
}

export interface OsintSourceStatus {
  adapter: string
  label: string
  status: 'ok' | 'skipped' | 'failed'
  reason: string
  evidence_ids: string[]
}

export interface OsintEvidenceItem {
  id: string
  source: string
  source_type: string
  url: string
  observed_at: string
  claim: string
  topic: string
  side: 'home' | 'away' | 'both' | 'neutral'
  confidence: number
  freshness: number
  raw_excerpt: string
}

export interface FactorImpact {
  factor_id: string
  label: string
  group: string
  enabled: boolean
  weight: number
  impact: number
  direction: 'home' | 'away' | 'draw' | 'neutral'
  confidence: number
  evidence_ids: string[]
  missing_reason: string
}

export interface PredictionResult {
  lean: 'home' | 'away' | 'draw' | 'home_or_draw' | 'away_or_draw' | 'info_insufficient'
  summary: string
  outcome_probabilities: OutcomeProbabilities
  primary_probability: number
  margin_to_runner_up: number
  clarity: 'clear' | 'close' | 'insufficient'
  scoreline_band: string[]
  drivers: string[]
  uncertainties: string[]
  sporttery_market: SportteryMarket | null
  handicap_conclusion: HandicapConclusion | null
}

export interface OutcomeProbabilities {
  home_win: number
  draw: number
  away_win: number
}

export interface OutcomeOdds {
  home_win: number
  draw: number
  away_win: number
}

export interface SportteryMarket {
  provider: 'sporttery'
  had_odds: OutcomeOdds | null
  had_implied_probabilities: OutcomeProbabilities
  home_handicap: number | null
  hhad_odds: OutcomeOdds | null
  hhad_implied_probabilities: OutcomeProbabilities | null
  observed_at: string
}

export interface HandicapConclusion {
  home_handicap: number
  outcome: 'home' | 'draw' | 'away'
  handicap_probabilities: OutcomeProbabilities
  probability: number
  margin_to_runner_up: number
  clarity: 'clear' | 'close'
}

export interface DataQualitySummary {
  insufficiency_reasons: string[]
  primary_insufficiency_reason: string
  source_summary: Record<string, number>
  fundamental_factor_count: number
  relevant_search_results_count: number
  dropped_search_results_count: number
  extraction_status: string
}

export interface ConfidenceRating {
  level: 'L1' | 'L2' | 'L3' | 'L4'
  reason: string
}

export interface IntelligenceCycleStage {
  name: '收集' | '加工' | '开发' | '生产'
  status: 'completed' | 'partial' | 'skipped'
  summary: string
}

export interface IntelligenceFinding {
  id: string
  statement: string
  finding_type: 'confirmed' | 'assessment'
  confidence_level: 'L1' | 'L2' | 'L3' | 'L4'
  evidence_ids: string[]
  source_summary: string
}

export interface FootballOsintJob {
  job_id: string
  status: OsintJobStatus
  phase: OsintJobPhase
  progress: number
  match: OsintMatch
  sources: OsintSourceStatus[]
  evidence: OsintEvidenceItem[]
  factors: FactorImpact[]
  prediction: PredictionResult | null
  confidence: ConfidenceRating | null
  data_quality?: DataQualitySummary | null
  intelligence_cycle: IntelligenceCycleStage[]
  confirmed_findings: IntelligenceFinding[]
  assessments: IntelligenceFinding[]
  alternative_explanations: string[]
  next_steps: string[]
  report_markdown: string
  error?: string
}

export interface TrackRecordEntry {
  home_team: string
  away_team: string
  kickoff_at: string
  predicted_lean: string
  predicted_scoreline_band: string[]
  actual_home_score: number
  actual_away_score: number
  lean_correct: boolean
  scoreline_hit: boolean
}

export interface TrackRecordLeanStat {
  lean: string
  settled: number
  accuracy: number
}

export interface TrackRecordStats {
  settled: number
  lean_accuracy?: number
  scoreline_accuracy?: number
  by_lean?: TrackRecordLeanStat[]
  best_lean?: TrackRecordLeanStat | null
  recent?: TrackRecordEntry[]
}

// ── v2: 赛后回看 & 多场对比 ───────────────────────────────────────────────────

export interface HistoryRecord {
  job_id: string
  home_team: string
  away_team: string
  kickoff_at: string
  competition: string
  predicted_lean: string
  predicted_scoreline_band: string[]
  actual_home_score: number
  actual_away_score: number
  actual_outcome: string
  lean_correct: boolean | null
  scoreline_hit: boolean | null
  settled_at: string
}

export interface Retrospective {
  hit_factors: string[]
  miss_factors: string[]
  note: string
}

export interface HistoryDetail {
  record: HistoryRecord
  factors?: FactorImpact[]
  retrospective?: Retrospective
  factors_expired?: boolean
}

export interface CompareItem {
  job_id: string
  home_team?: string
  away_team?: string
  kickoff_at?: string
  competition?: string
  predicted_lean?: string | null
  confidence_level?: string | null
  evidence_summary?: { strong: number; weak: number; insufficient: number }
  top_uncertainties?: string[]
  factor_completeness?: string
  error?: string
}
