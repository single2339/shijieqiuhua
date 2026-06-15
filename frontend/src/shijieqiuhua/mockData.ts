import type { FixtureStatus, FootballMatch, MatchQuestion } from './types'

export const QUESTION_PRESETS: MatchQuestion[] = [
  { id: 'half', label: '半场', prompt: '上半场比分预计是多少？' },
  { id: 'cards', label: '红黄牌', prompt: '全场红黄牌的预测数量是多少？' },
  { id: 'corners', label: '角球', prompt: '全场角球数预测是多少？' },
  { id: 'goals', label: '进球数', prompt: '全场比分预测是多少？' },
  { id: 'player', label: '球员', prompt: '核心球员状态会怎样影响比赛？' },
  { id: 'risk', label: '风险', prompt: '这场比赛最大的临场风险是什么？' },
]

const STATUS_LABELS: Record<FixtureStatus['status'], string> = {
  scheduled: '未开赛',
  live: '进行中',
  finished: '已结束',
}

export function fixtureToMatch(fixture: FixtureStatus): FootballMatch {
  const scoreLabel = fixture.home_score != null && fixture.away_score != null
    ? `${STATUS_LABELS[fixture.status]} ${fixture.home_score}-${fixture.away_score}`
    : STATUS_LABELS[fixture.status]
  return {
    id: `dqd-${fixture.id}`,
    league: fixture.league,
    kickoffAt: fixture.kickoff_at,
    homeTeam: fixture.home_team,
    awayTeam: fixture.away_team,
    publicLean: scoreLabel,
    questions: [...QUESTION_PRESETS],
  }
}

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
