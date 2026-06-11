import type { ActivationCode, FootballMatch, InvitationCode, MatchQuestion } from './types'

export const QUESTION_PRESETS: MatchQuestion[] = [
  { id: 'half', label: '半场', prompt: '上半场哪一方更容易占据主动？' },
  { id: 'cards', label: '红黄牌', prompt: '本场红黄牌风险是否偏高？' },
  { id: 'corners', label: '角球', prompt: '上半场角球会不会偏多？' },
  { id: 'goals', label: '进球数', prompt: '全场进球数压力更偏大还是偏小？' },
  { id: 'player', label: '球员', prompt: '核心球员状态会怎样影响比赛？' },
  { id: 'risk', label: '风险', prompt: '这场比赛最大的临场风险是什么？' },
]

export const MATCHES: FootballMatch[] = [
  {
    id: 'wc-arg-ksa',
    league: '世界杯 A组',
    kickoffAt: '今晚 20:00',
    homeTeam: '阿根廷',
    awayTeam: '沙特阿拉伯',
    publicLean: '主队方向略优',
    prediction: {
      home: 68,
      draw: 21,
      away: 11,
      confidence: 74,
      rating: 'L2',
      summary: '主队前场创造力与核心球员状态更稳定，但客队中场拦截效率会压低结论强度。',
    },
    questions: [...QUESTION_PRESETS],
    evidence: [
      { id: 'e1', strength: 'strong', title: '核心攻击手近三场参与进球稳定', source: 'team-form-feed' },
      { id: 'e2', strength: 'weak', title: '客队中场拦截效率稳定，具备限制节奏能力', source: 'match-preview' },
      { id: 'e3', strength: 'insufficient', title: '裁判出牌尺度样本不足，红牌结论需谨慎', source: 'referee-watch' },
    ],
    riskFlags: ['赛前名单仍有不确定性', '不使用市场价格模型'],
  },
  {
    id: 'wc-pol-mex',
    league: '世界杯 A组',
    kickoffAt: '今晚 23:00',
    homeTeam: '波兰',
    awayTeam: '墨西哥',
    publicLean: '平局压力偏高',
    prediction: {
      home: 34,
      draw: 36,
      away: 30,
      confidence: 61,
      rating: 'L3',
      summary: '双方防守完整度接近，比赛可能更依赖定位球和半场节奏变化。',
    },
    questions: [...QUESTION_PRESETS],
    evidence: [
      { id: 'e4', strength: 'strong', title: '双方近期失球控制都较稳定', source: 'form-check' },
      { id: 'e5', strength: 'weak', title: '客队边路推进可能制造角球数量', source: 'tactical-brief' },
      { id: 'e6', strength: 'insufficient', title: '临场天气对节奏影响暂不明确', source: 'venue-weather' },
    ],
    riskFlags: ['平局压力较高', '角球结论需要临场阵容确认'],
  },
  {
    id: 'wc-bra-srb',
    league: '世界杯 D组',
    kickoffAt: '明晚 20:00',
    homeTeam: '巴西',
    awayTeam: '塞尔维亚',
    publicLean: '主队方向占优',
    prediction: {
      home: 72,
      draw: 18,
      away: 10,
      confidence: 78,
      rating: 'L2',
      summary: '主队前场转换速度和个人突破优势明显，客队定位球仍是主要风险来源。',
    },
    questions: [...QUESTION_PRESETS],
    evidence: [
      { id: 'e7', strength: 'strong', title: '主队前场转换速度优势明显', source: 'player-index' },
      { id: 'e8', strength: 'weak', title: '客队高点定位球可能制造防守压力', source: 'tactical-brief' },
      { id: 'e9', strength: 'insufficient', title: '轮换名单未确认，半场判断需保守', source: 'squad-watch' },
    ],
    riskFlags: ['定位球防守风险', '轮换名单未完全确认'],
  },
]

export const INVITATIONS: InvitationCode[] = [
  { code: 'QH-2026-SEED', inviterId: 'seed-user', expiresAt: '2026-12-31T23:59:59.000Z' },
  { code: 'USED-2026', inviterId: 'seed-user', usedBy: 'u-old', expiresAt: '2026-12-31T23:59:59.000Z' },
]

export const ACTIVATION_CODES: ActivationCode[] = [
  { code: 'PAY-2026-FULL', used: false },
]
