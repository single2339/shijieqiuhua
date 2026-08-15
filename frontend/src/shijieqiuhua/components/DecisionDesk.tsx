import {
  CheckCircle, ChartLineUp, Clock, Info, Pulse, ShieldCheck,
  TrendDown, TrendUp, WarningCircle, XCircle,
} from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import type { ActualResult, MarketComparison, MarketConsensus, MarketSourceSnapshot, MatchDecision, OutcomeProbabilities, PostMatchReview, SystemPrediction } from '../types'

interface DecisionDeskProps {
  decision?: MatchDecision | null
  loading?: boolean
  error?: string | null
}

const OUTCOME_LABEL: Record<string, string> = {
  home: '主队占优',
  away: '客队占优',
  draw: '平局倾向',
  home_or_draw: '主队不败',
  away_or_draw: '客队不败',
  home_win: '主胜方向',
  away_win: '客胜方向',
  info_insufficient: '暂不形成方向',
}

const CONFIDENCE_LABEL: Record<string, string> = {
  L1: '确认', L2: '高可信', L3: '中可信', L4: '推测',
}

const PROBABILITY_LABEL: Record<keyof OutcomeProbabilities, string> = {
  home_win: '主胜', draw: '平局', away_win: '客胜',
}

export default function DecisionDesk({ decision, loading = false, error }: DecisionDeskProps) {
  if (loading) return <DecisionDeskSkeleton />
  if (error) return <DecisionDeskState kind="error" message={error} />
  if (!decision) return <DecisionDeskState kind="empty" message="选择一场比赛后，这里会显示完整赛果研判。" />

  const match = decision.match
  const title = match ? `${match.home_team} vs ${match.away_team}` : '比赛决策台'

  return (
    <motion.section
      className="sqh-decision-desk"
      aria-label={`${title} 决策台`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.2, 0.7, 0.3, 1] }}
    >
      <header className="sqh-decision-desk__header">
        <div>
          <p className="sqh-decision-eyebrow"><Pulse size={14} weight="bold" />比赛决策台</p>
          <h2>{title}</h2>
          {match && <p className="sqh-decision-meta">{match.competition || '赛事待确认'} · {formatKickoff(match.kickoff_at)} · {statusDetail(decision.fixture_status)}</p>}
        </div>
        <div className={`sqh-decision-status sqh-decision-status--${decision.fixture_status}`}>
          <span />{statusLabel(decision.fixture_status)}
        </div>
      </header>

      {decision.fixture_status === 'finished' && decision.actual_result && (
        <FinishedReview actual={decision.actual_result} review={decision.review} />
      )}

      <div className="sqh-decision-desk__grid">
        <SystemVerdictPanel decision={decision} />
        <MarketConsensusPanel consensus={decision.market_consensus} sources={decision.market_sources} />
      </div>

      <MarketComparisonPanel comparison={decision.market_comparison} />

      <footer className="sqh-decision-disclaimer"><Info size={14} weight="duotone" />{decision.disclaimer}</footer>
    </motion.section>
  )
}

export function SystemVerdictPanel({ decision }: { decision: MatchDecision }) {
  const prediction = decision.model_prediction
  const probabilities = prediction?.outcome_probabilities ?? decision.outcome_probabilities
  const isInsufficient = decision.outcome === 'info_insufficient'

  return (
    <article className={`sqh-decision-panel sqh-decision-panel--system${isInsufficient ? ' sqh-decision-panel--limited' : ''}`}>
      <div className="sqh-decision-panel__topline"><span>系统研判</span><ShieldCheck size={19} weight="duotone" /></div>
      <div className="sqh-system-verdict-row">
        <div>
          <h3>{OUTCOME_LABEL[prediction?.lean ?? decision.outcome] || '暂不形成方向'}</h3>
          <p>{prediction?.summary || decision.reason || '系统仍在等待足够的信息形成结论。'}</p>
        </div>
        {decision.confidence && <span className={`sqh-decision-confidence sqh-decision-confidence--${decision.confidence.level}`}>{CONFIDENCE_LABEL[decision.confidence.level] || decision.confidence.level}</span>}
      </div>

      {!isInsufficient && probabilities && <ProbabilityStrip probabilities={probabilities} />}

      <div className="sqh-system-scoreline">
        <span>预测比分</span>
        <strong>{prediction?.scoreline_band?.length ? prediction.scoreline_band.join(' / ') : '暂未形成比分倾向'}</strong>
      </div>

      {prediction?.drivers?.length ? (
        <div className="sqh-system-drivers">
          <span>研判依据</span>
          <ul>{prediction.drivers.slice(0, 3).map((driver) => <li key={driver}>{driver}</li>)}</ul>
        </div>
      ) : null}
      {decision.confidence?.reason && <p className="sqh-system-confidence-note">置信度依据：{decision.confidence.reason}</p>}
    </article>
  )
}

export function MarketConsensusPanel({ consensus, sources }: { consensus?: MarketConsensus; sources: MarketSourceSnapshot[] }) {
  const probabilities = consensus?.probabilities
  const hasConsensus = consensus?.status === 'consensus' && probabilities
  const count = consensus?.fresh_source_count ?? 0

  return (
    <article className="sqh-decision-panel sqh-decision-panel--market">
      <div className="sqh-decision-panel__topline"><span>市场共识</span><ChartLineUp size={19} weight="duotone" /></div>
      {hasConsensus ? (
        <>
          <div className="sqh-market-summary">
            <div><strong>{OUTCOME_LABEL[leadingOutcome(probabilities)]}</strong><span>{count} 个新鲜来源</span></div>
            <p>仅汇总授权的主流赔率来源，不参与系统预测。</p>
          </div>
          <ProbabilityStrip probabilities={probabilities} />
        </>
      ) : (
        <div className="sqh-market-fallback">
          <WarningCircle size={21} weight="duotone" />
          <div><strong>市场共识暂不可用</strong><p>{count > 0 ? `仅获得 ${count} 个新鲜来源，未达到共识门槛。` : '暂未获得足够的新鲜授权来源。'}</p></div>
        </div>
      )}

      {sources.length > 0 && (
        <div className="sqh-market-sources" aria-label="市场来源">
          {sources.map((source) => <MarketSourceRow key={`${source.source_id}-${source.observed_at}`} source={source} />)}
        </div>
      )}
    </article>
  )
}

export function MarketComparisonPanel({ comparison }: { comparison: MarketComparison }) {
  if (comparison.status === 'limited') {
    return <section className="sqh-market-comparison sqh-market-comparison--limited"><Info size={17} weight="duotone" /><span>暂不比较模型与市场</span><p>市场来源数量或新鲜度未达到对照要求。</p></section>
  }

  const aligned = comparison.status === 'aligned'
  const delta = typeof comparison.leader_delta === 'number' ? ` · 领先差 ${Math.round(comparison.leader_delta * 100)} 个百分点` : ''
  return (
    <section className={`sqh-market-comparison sqh-market-comparison--${comparison.status}`}>
      {aligned ? <CheckCircle size={18} weight="fill" /> : <WarningCircle size={18} weight="fill" />}
      <div>
        <strong>{aligned ? '模型与市场方向一致' : '模型与市场存在分歧'}</strong>
        <p>系统：{OUTCOME_LABEL[comparison.model_leader ?? ''] || '—'} · 市场：{OUTCOME_LABEL[comparison.market_leader ?? ''] || '—'}{delta}</p>
      </div>
    </section>
  )
}

function ProbabilityStrip({ probabilities }: { probabilities: OutcomeProbabilities }) {
  const entries = (Object.keys(PROBABILITY_LABEL) as Array<keyof OutcomeProbabilities>)
  const leader = leadingOutcome(probabilities)
  return <div className="sqh-decision-probabilities">
    {entries.map((key) => {
      const percent = Math.round(probabilities[key] * 100)
      return <div className={leader === key ? 'sqh-decision-probability sqh-decision-probability--lead' : 'sqh-decision-probability'} key={key}>
        <div><span>{PROBABILITY_LABEL[key]}</span><strong>{percent}%</strong></div>
        <i style={{ width: `${Math.max(4, percent)}%` }} />
      </div>
    })}
  </div>
}

function MarketSourceRow({ source }: { source: MarketSourceSnapshot }) {
  const observed = freshnessLabel(source.observed_at)
  const stale = isStale(source.observed_at)
  return <div className={`sqh-market-source${stale ? ' sqh-market-source--stale' : ''}`}>
    <div><strong>{source.display_name}</strong><span>{observed}</span></div>
    <span className="sqh-market-source-odds">{source.odds.home_win.toFixed(2)} · {source.odds.draw.toFixed(2)} · {source.odds.away_win.toFixed(2)}</span>
  </div>
}

function FinishedReview({ actual, review }: { actual: ActualResult; review?: PostMatchReview }) {
  return <section className="sqh-finished-review">
    <div className="sqh-finished-review__header"><span>赛后回看</span><Clock size={17} weight="duotone" /></div>
    <div className="sqh-finished-score"><span>最终比分</span><strong>{actual.home_score} - {actual.away_score}</strong><span>{OUTCOME_LABEL[actual.outcome] || actual.outcome}</span></div>
    {review && <div className="sqh-finished-results">
      {typeof review.lean_correct === 'boolean' && <ReviewPill hit={review.lean_correct} hitLabel="方向命中" missLabel="方向未中" />}
      {typeof review.scoreline_hit === 'boolean' && <ReviewPill hit={review.scoreline_hit} hitLabel="比分命中" missLabel="比分未命中" />}
      {review.summary && <p>{review.summary}</p>}
    </div>}
  </section>
}

function ReviewPill({ hit, hitLabel, missLabel }: { hit: boolean; hitLabel: string; missLabel: string }) {
  return <span className={hit ? 'sqh-review-pill sqh-review-pill--hit' : 'sqh-review-pill sqh-review-pill--miss'}>{hit ? <CheckCircle size={14} weight="fill" /> : <XCircle size={14} weight="fill" />}{hit ? hitLabel : missLabel}</span>
}

function DecisionDeskSkeleton() {
  return <section className="sqh-decision-skeleton" aria-label="正在生成比赛决策">
    <div className="sqh-decision-skeleton__line sqh-decision-skeleton__line--short" />
    <div className="sqh-decision-skeleton__line sqh-decision-skeleton__line--title" />
    <div className="sqh-decision-skeleton__grid"><i /><i /></div>
    <div className="sqh-decision-skeleton__line" />
  </section>
}

function DecisionDeskState({ kind, message }: { kind: 'empty' | 'error'; message: string }) {
  const Icon = kind === 'error' ? WarningCircle : Pulse
  return <section className={`sqh-decision-state sqh-decision-state--${kind}`}><Icon size={24} weight="duotone" /><div><strong>{kind === 'error' ? '无法加载比赛决策' : '尚未选择比赛'}</strong><p>{message}</p></div></section>
}

function leadingOutcome(probabilities: OutcomeProbabilities): keyof OutcomeProbabilities {
  return (Object.keys(probabilities) as Array<keyof OutcomeProbabilities>).reduce((leader, current) => probabilities[current] > probabilities[leader] ? current : leader, 'home_win')
}

function formatKickoff(value?: string | null): string {
  if (!value) return '开球时间待确认'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
}

function freshnessLabel(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '更新时间待确认'
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60_000))
  if (minutes < 2) return '刚刚更新'
  if (minutes > 30) return `数据已过期 · ${minutes < 60 ? `${minutes} 分钟` : `${Math.floor(minutes / 60)} 小时`}前更新`
  if (minutes < 60) return `${minutes} 分钟前更新`
  return `${minutes < 60 ? minutes : Math.floor(minutes / 60)} ${minutes < 60 ? '分钟' : '小时'}前更新`
}

function isStale(value: string): boolean {
  const date = new Date(value)
  return !Number.isNaN(date.getTime()) && Date.now() - date.getTime() > 30 * 60_000
}

function statusLabel(status: MatchDecision['fixture_status']): string {
  return status === 'finished' ? '已结束' : status === 'live' ? '赛前研判' : '赛前'
}

function statusDetail(status: MatchDecision['fixture_status']): string {
  return status === 'live' ? '赛前研判，截至开赛前' : statusLabel(status)
}
