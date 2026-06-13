import type { FactorImpact, OsintEvidenceItem } from '../types'
import { byStrength } from './evidence'

interface Props {
  evidence: OsintEvidenceItem[]
  factors: FactorImpact[]
}

export default function EvidenceStrength({ evidence, factors }: Props) {
  if (!evidence.length) return null

  const buckets = byStrength(evidence)
  const missing = factors
    .filter(f => !f.enabled && f.missing_reason)
    .map(f => f.missing_reason)

  return (
    <section>
      <div className="sqh-section-title"><span>证据强弱</span></div>
      <div className="sqh-evidence-grid">
        <Col label="强证据" items={buckets.strong} mod="strong" />
        <Col label="弱信号" items={buckets.weak} mod="weak" />
        <Col label="样本不足" items={buckets.insufficient} mod="insufficient" />
      </div>
      {missing.length > 0 && (
        <ul className="sqh-missing-list">
          {missing.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </section>
  )
}

function Col({ label, items, mod }: { label: string; items: OsintEvidenceItem[]; mod: string }) {
  return (
    <div className={`sqh-evidence-col sqh-evidence-col--${mod}`}>
      <strong>{label} · {items.length}</strong>
      {items.slice(0, 5).map(ev => (
        <div key={ev.id} className="sqh-evidence-item">
          <span className="sqh-evidence-source">{ev.source}</span>
          {ev.claim.slice(0, 120)}
        </div>
      ))}
    </div>
  )
}
