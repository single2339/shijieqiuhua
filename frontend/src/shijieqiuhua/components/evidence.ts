/** Evidence classification — mirrors backend/evidence.py thresholds. */
import type { OsintEvidenceItem } from '../types'

export const STRONG = 0.5
export const WEAK = 0.25

export function classifyStrength(c: number): 'strong' | 'weak' | 'insufficient' {
  if (c >= STRONG) return 'strong'
  if (c >= WEAK) return 'weak'
  return 'insufficient'
}

export function byStrength(items: OsintEvidenceItem[]) {
  const buckets: Record<string, OsintEvidenceItem[]> = { strong: [], weak: [], insufficient: [] }
  for (const ev of items) buckets[classifyStrength(ev.confidence)].push(ev)
  return buckets
}
