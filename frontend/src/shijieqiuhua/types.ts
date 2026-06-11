export type AccessMode = 'public' | 'registered_unpaid' | 'paid'
export type QuestionDimension = 'half' | 'cards' | 'corners' | 'goals' | 'player' | 'risk'
export type EvidenceStrength = 'strong' | 'weak' | 'insufficient'

export interface UserProfile {
  id: string
  name: string
  status: Exclude<AccessMode, 'public'>
  inviteCodeUsed: string
}

export interface InvitationCode {
  code: string
  inviterId: string
  usedBy?: string
  expiresAt: string
}

export interface ActivationCode {
  code: string
  used: boolean
  redeemedBy?: string
}

export interface EvidenceItem {
  id: string
  strength: EvidenceStrength
  title: string
  source: string
}

export interface MatchQuestion {
  id: QuestionDimension
  label: string
  prompt: string
}

export interface MatchPrediction {
  home: number
  draw: number
  away: number
  confidence: number
  rating: 'L1' | 'L2' | 'L3' | 'L4'
  summary: string
}

export interface FootballMatch {
  id: string
  league: string
  kickoffAt: string
  homeTeam: string
  awayTeam: string
  publicLean: string
  prediction: MatchPrediction
  questions: MatchQuestion[]
  evidence: EvidenceItem[]
  riskFlags: string[]
}
