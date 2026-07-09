import type { HistoryRecord } from './types'

function historyResultKey(record: HistoryRecord): string {
  return [
    record.competition.trim(),
    record.home_team.trim(),
    record.away_team.trim(),
    record.kickoff_at.trim(),
    record.actual_home_score,
    record.actual_away_score,
    record.actual_outcome,
  ].join('\u0000')
}

export function dedupeHistoryRecords(records: HistoryRecord[]): HistoryRecord[] {
  const seen = new Set<string>()
  return records.filter(record => {
    const key = historyResultKey(record)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
