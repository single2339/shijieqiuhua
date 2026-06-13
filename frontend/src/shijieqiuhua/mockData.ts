import type { FootballMatch, MatchQuestion } from './types'

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
    questions: [...QUESTION_PRESETS],
  },
  {
    id: 'wc-pol-mex',
    league: '世界杯 A组',
    kickoffAt: '今晚 23:00',
    homeTeam: '波兰',
    awayTeam: '墨西哥',
    publicLean: '平局压力偏高',
    questions: [...QUESTION_PRESETS],
  },
  {
    id: 'wc-bra-srb',
    league: '世界杯 D组',
    kickoffAt: '明晚 20:00',
    homeTeam: '巴西',
    awayTeam: '塞尔维亚',
    publicLean: '主队方向占优',
    questions: [...QUESTION_PRESETS],
  },
]
