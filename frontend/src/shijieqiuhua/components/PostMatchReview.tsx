import { ArrowRight, CheckCircle, Lock, XCircle } from '@phosphor-icons/react'
import type { HistoryDetail } from '../types'
import type { UserTier } from './AuthGate'

const LEAN_LABEL: Record<string, string> = {
  home: '主队占优', away: '客队占优', draw: '平局倾向',
  home_or_draw: '主队不败', away_or_draw: '客队不败',
  info_insufficient: '信息不足',
}
const OUTCOME_LABEL: Record<string, string> = {
  home: '主队赢', away: '客队赢', draw: '平局',
}
const HANDICAP_OUTCOME_LABEL: Record<string, string> = {
  home: '让胜', away: '让负', draw: '让平',
}

interface PostMatchReviewProps {
  detail: HistoryDetail | null
  loading: boolean
  userTier: UserTier
  onUpgrade?: () => void
}

export default function PostMatchReview({ detail, loading, userTier, onUpgrade }: PostMatchReviewProps) {
  if (loading) return <div className="sqh-pmr-loading">加载回顾中…</div>
  if (!detail) return null

  const { record, retrospective, factors_expired } = detail
  const canDeep = userTier === 'paid'
  const handicap = record.sporttery_handicap
  const handicapSummary = handicap && `体彩让球（主队 ${handicap.home_handicap >= 0 ? '+' : ''}${handicap.home_handicap}）｜研判：${HANDICAP_OUTCOME_LABEL[handicap.predicted_outcome]}（${Math.round(handicap.predicted_probability * 100)}%）｜赛果：${handicap.actual_outcome ? HANDICAP_OUTCOME_LABEL[handicap.actual_outcome] : '—'}｜${handicap.correct === true ? '命中' : handicap.correct === false ? '未中' : '待结算'}`

  return (
    <div className="sqh-pmr">
      <div className="sqh-pmr-header">
        <div className="sqh-pmr-competition">{record.competition}</div>
        <div className="sqh-pmr-teams">
          <span>{record.home_team}</span>
          <div className="sqh-pmr-score">
            {record.actual_home_score} - {record.actual_away_score}
          </div>
          <span>{record.away_team}</span>
        </div>
        <div className="sqh-pmr-meta">{record.kickoff_at} · 已结束</div>
      </div>

      <div className="sqh-pmr-grid">
        <div className="sqh-pmr-cell">
          <div className="sqh-pmr-cell-label">系统研判</div>
          <div className="sqh-pmr-cell-value">{LEAN_LABEL[record.predicted_lean] ?? record.predicted_lean}</div>
        </div>
        <div className="sqh-pmr-cell">
          <div className="sqh-pmr-cell-label">预测比分带</div>
          <div className="sqh-pmr-cell-value">{record.predicted_scoreline_band.join(' / ') || '—'}</div>
        </div>
        <div className="sqh-pmr-cell">
          <div className="sqh-pmr-cell-label">实际结果</div>
          <div className="sqh-pmr-cell-value">{OUTCOME_LABEL[record.actual_outcome] ?? record.actual_outcome}</div>
        </div>
      </div>

      <div className="sqh-pmr-badges">
        {record.predicted_lean === 'info_insufficient' ? (
          <span className="sqh-pmr-badge">信息不足，未计入命中率</span>
        ) : (
          <>
            <span className={`sqh-pmr-badge ${record.lean_correct ? 'sqh-pmr-badge--hit' : 'sqh-pmr-badge--miss'}`}>
              {record.lean_correct
                ? <><CheckCircle size={13} weight="fill" /> 方向命中</>
                : <><XCircle size={13} weight="fill" /> 方向未中</>
              }
            </span>
            <span className={`sqh-pmr-badge ${record.scoreline_hit ? 'sqh-pmr-badge--hit' : 'sqh-pmr-badge--miss'}`}>
              {record.scoreline_hit
                ? <><CheckCircle size={13} weight="fill" /> 比分命中</>
                : <><XCircle size={13} weight="fill" /> 比分未中</>
              }
            </span>
          </>
        )}
      </div>

      {handicapSummary && <div className="sqh-pmr-handicap">{handicapSummary}</div>}

      <div className={canDeep ? '' : 'sqh-report-locked'}>
        {!canDeep && (
          <div className="sqh-report-veil">
            <div className="sqh-report-veil-inner">
              <Lock size={24} weight="duotone" />
              <b>开通后查看完整因子分析</b>
              {onUpgrade && (
                <button className="sqh-unlock-btn" onClick={onUpgrade}>
                  开通完整功能 <ArrowRight size={14} weight="bold" />
                </button>
              )}
            </div>
          </div>
        )}
        {canDeep && (
          <div>
            {factors_expired ? (
              <div className="sqh-pmr-expired">因子数据已过期，无法展示详细回顾。</div>
            ) : retrospective ? (
              <div className="sqh-pmr-retro">
                <div className="sqh-pmr-retro-title">关键因子回顾</div>
                {retrospective.hit_factors.length > 0 && (
                  <ul className="sqh-pmr-factor-list sqh-pmr-factor-list--hit">
                    {retrospective.hit_factors.map(f => (
                      <li key={f}><CheckCircle size={12} weight="fill" />{f}</li>
                    ))}
                  </ul>
                )}
                {retrospective.miss_factors.length > 0 && (
                  <ul className="sqh-pmr-factor-list sqh-pmr-factor-list--miss">
                    {retrospective.miss_factors.map(f => (
                      <li key={f}><XCircle size={12} weight="fill" />{f}</li>
                    ))}
                  </ul>
                )}
                <p className="sqh-pmr-retro-note">{retrospective.note}</p>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
