import { X } from '@phosphor-icons/react'
import type { CompareItem } from '../types'

const LEAN_LABEL: Record<string, string> = {
  home: '主队占优', away: '客队占优', draw: '平局倾向',
  home_or_draw: '主队不败', away_or_draw: '客队不败',
  info_insufficient: '信息不足',
}

interface ComparePanelProps {
  results: CompareItem[]
  loading: boolean
  onClose: () => void
}

type RowDef = { label: string; render: (r: CompareItem) => string }

const ROWS: RowDef[] = [
  { label: '研判倾向', render: r => r.predicted_lean ? (LEAN_LABEL[r.predicted_lean] ?? r.predicted_lean) : '—' },
  { label: '置信度',   render: r => r.confidence_level ?? '—' },
  { label: '强证据',   render: r => r.evidence_summary != null ? String(r.evidence_summary.strong) : '—' },
  { label: '弱信号',   render: r => r.evidence_summary != null ? String(r.evidence_summary.weak) : '—' },
  { label: '信息完整度', render: r => r.factor_completeness ?? '—' },
  { label: '主要风险', render: r => r.top_uncertainties?.join('；') || '—' },
]

export default function ComparePanel({ results, loading, onClose }: ComparePanelProps) {
  return (
    <div className="sqh-compare-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="sqh-compare-panel">
        <div className="sqh-compare-hd">
          <span className="sqh-compare-title">多场对比</span>
          <button className="sqh-compare-close" onClick={onClose}><X size={16} weight="bold" /></button>
        </div>

        {loading ? (
          <div className="sqh-compare-loading">加载中…</div>
        ) : (
          <div className="sqh-compare-table">
            <div className="sqh-compare-row sqh-compare-row--header">
              <div className="sqh-compare-dim" />
              {results.map(r => (
                <div key={r.job_id} className="sqh-compare-col sqh-compare-col--header">
                  {r.error ? '—' : `${r.home_team} vs ${r.away_team}`}
                </div>
              ))}
            </div>
            {ROWS.map(row => (
              <div key={row.label} className="sqh-compare-row">
                <div className="sqh-compare-dim">{row.label}</div>
                {results.map(r => (
                  <div key={r.job_id} className="sqh-compare-col">
                    {r.error
                      ? <span className="sqh-compare-error">{r.error}</span>
                      : row.render(r)
                    }
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
