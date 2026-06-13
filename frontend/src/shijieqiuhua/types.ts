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
  homeTeam: string
  awayTeam: string
  publicLean: string
  questions: MatchQuestion[]
}

export type OsintJobStatus = 'queued' | 'running' | 'needs_review' | 'completed' | 'failed'
export type OsintJobPhase = 'queued' | 'verify' | 'collect' | 'normalize' | 'score' | 'report' | 'done'

export interface FootballOsintJobRequest {
  home_team: string
  away_team: string
  kickoff_at?: string
  competition?: string
  venue?: string
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
  lean: 'home' | 'away' | 'draw' | 'home_or_draw' | 'away_or_draw'
  summary: string
  probability_band: Record<'home_win' | 'draw' | 'away_win', [number, number]>
  scoreline_band: string[]
  drivers: string[]
  uncertainties: string[]
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
  intelligence_cycle: IntelligenceCycleStage[]
  confirmed_findings: IntelligenceFinding[]
  assessments: IntelligenceFinding[]
  alternative_explanations: string[]
  next_steps: string[]
  report_markdown: string
  error?: string
}
