import { useState } from 'react'
import {
  ArrowRight, CheckCircle, Clock, Gauge, Info, ListChecks,
  Lock, MagnifyingGlass, Scales, WarningCircle,
} from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { byStrength } from './evidence'
import type { FactorImpact, FootballOsintJob, IntelligenceFinding, OsintEvidenceItem } from '../types'
import type { UserTier } from './AuthGate'

// ── public API ──

interface ReportViewProps {
  osintJob: FootballOsintJob | null
  userTier: UserTier
  onUpgrade?: () => void
}

type TabKey = 'cycle' | 'factors' | 'evidence' | 'findings' | 'next'

export default function ReportView({ osintJob, userTier, onUpgrade }: ReportViewProps) {
  const [activeTab, setActiveTab] = useState<TabKey | null>(null)

  if (!osintJob) return null

  const {
    prediction, confidence, intelligence_cycle,
    factors, evidence, confirmed_findings, assessments,
    alternative_explanations, next_steps,
  } = osintJob

  const canDeep = userTier === 'paid'

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = []
  if (intelligence_cycle.length > 0) tabs.push({ key: 'cycle', label: '情报循环', icon: <ListChecks size={14} weight="duotone" /> })
  if (factors.length > 0) tabs.push({ key: 'factors', label: '因子权重', icon: <Gauge size={14} weight="duotone" /> })
  if (evidence.length > 0) tabs.push({ key: 'evidence', label: '证据链', icon: <MagnifyingGlass size={14} weight="duotone" /> })
  if (confirmed_findings.length > 0 || assessments.length > 0) tabs.push({ key: 'findings', label: '确认 / 推断', icon: <CheckCircle size={14} weight="duotone" /> })
  if (alternative_explanations.length > 0 || next_steps.length > 0) tabs.push({ key: 'next', label: '替代 / 下一步', icon: <Clock size={14} weight="duotone" /> })

  const activeKey = tabs.some(t => t.key === activeTab) ? (activeTab as TabKey) : tabs[0]?.key

  return (
    <motion.div
      className="sqh-report-root"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0.7, 0.3, 1] }}
    >
      {/* ── verdict ── */}
      {prediction && <VerdictCard prediction={prediction} confidence={confidence} />}

      {/* ── gated sections ── */}
      {tabs.length > 0 && (
        canDeep ? (
          <details className="sqh-analysis-disclosure">
            <summary><ListChecks size={16} weight="duotone" />查看完整分析过程</summary>
            <div className="sqh-analysis-disclosure-body">
              <div className="sqh-tabbar">
                {tabs.map(t => (
                  <button
                    key={t.key}
                    className={`sqh-tab${activeKey === t.key ? ' sqh-tab--on' : ''}`}
                    onClick={() => setActiveTab(t.key)}
                  >
                    {t.icon}{t.label}
                  </button>
                ))}
              </div>

              <div className="sqh-rsec sqh-tabpanel">
                <div className="sqh-rsec-bd">
                  {activeKey === 'cycle' && <IntelCycle stages={intelligence_cycle} />}
                  {activeKey === 'factors' && <FactorBars factors={factors} />}
                  {activeKey === 'evidence' && <EvidenceList items={evidence} />}

                  {activeKey === 'findings' && (
                    <div className="sqh-findings-row">
                      {confirmed_findings.length > 0 && (
                        <div>
                          <div className="sqh-tabsub-hd"><CheckCircle size={15} weight="duotone" />确认事实</div>
                          <FindingList items={confirmed_findings} />
                        </div>
                      )}
                      {assessments.length > 0 && (
                        <div>
                          <div className="sqh-tabsub-hd"><Scales size={15} weight="duotone" />研判推断</div>
                          <FindingList items={assessments} />
                        </div>
                      )}
                    </div>
                  )}

                  {activeKey === 'next' && (
                    <>
                      {alternative_explanations.length > 0 && (
                        <>
                          <div className="sqh-tabsub-hd"><WarningCircle size={15} weight="duotone" />替代解释</div>
                          <ul className="sqh-bullet-list" style={{ marginBottom: 16 }}>
                            {alternative_explanations.map((a, i) => <li key={i}>{a}</li>)}
                          </ul>
                        </>
                      )}
                      <div className="sqh-tabsub-hd"><Clock size={15} weight="duotone" />下一步 / 复扫计划</div>
                      <ul className="sqh-bullet-list">
                        {next_steps.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                      {confidence?.reason && (
                        <p className="sqh-conf-reason">
                          <Info size={13} weight="duotone" /> 置信度依据：{confidence.reason}
                        </p>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          </details>
        ) : (
          <div className="sqh-report-lock-card">
            <Lock size={28} weight="duotone" />
            <b>开通完整功能后查看</b>
            <p>证据链、因子权重与情报轨迹是研判的依据所在。</p>
            {onUpgrade && (
              <button className="sqh-unlock-btn" onClick={onUpgrade}>
                开通完整功能 <ArrowRight size={15} weight="bold" />
              </button>
            )}
          </div>
        )
      )}
    </motion.div>
  )
}

// ──────────────────────── sub-components ────────────────────────

// ── VerdictCard ──

const CONF_LABELS: Record<string, string> = { L1: '确认', L2: '高可信', L3: '中可信', L4: '推测' }

const LEAN_LABEL: Record<string, string> = {
  home: '主胜方向',
  away: '客胜方向',
  draw: '平局方向',
  home_or_draw: '主队不败方向',
  away_or_draw: '客队不败方向',
  info_insufficient: '信息不足',
}

export function dataQualityReasonLabel(code: string): string {
  const labels: Record<string, string> = {
    detail_fixture_unmatched: '赛前分析源暂未匹配到该场',
    structured_stats_unresolved: '结构化战绩源未解析到双方近期数据',
    irrelevant_search_results: '搜索结果多为百科或泛介绍',
    no_relevant_search_results: '未找到同时覆盖双方的赛前报道',
    llm_extraction_empty: '已有文本未抽取出关键基本面字段',
    source_runtime_failure: '部分数据源暂时不可用',
    too_early: '赛前信息可能尚未发布',
    no_user_supplied_context: '尚未收到用户补充信息',
  }
  return labels[code] || code
}

function ConfBadge({ level }: { level: string }) {
  return (
    <span className={`sqh-cbadge sqh-cbadge--${level}`}>
      {CONF_LABELS[level] || level}
    </span>
  )
}

function VerdictCard({ prediction, confidence }: {
  prediction: NonNullable<FootballOsintJob['prediction']>
  confidence: FootballOsintJob['confidence']
}) {
  const insufficient = prediction.lean === 'info_insufficient'

  return (
    <div className={`sqh-verdict${insufficient ? ' sqh-verdict--insufficient' : ''}`}>
      <div className="sqh-verdict-top">
        <div>
          <div className="sqh-verdict-headline">
            {LEAN_LABEL[prediction.lean] || prediction.lean}
          </div>
        </div>
        {confidence && <ConfBadge level={confidence.level} />}
      </div>

      <p className="sqh-verdict-summary">{prediction.summary}</p>

      <ProbabilityBands
        probabilities={prediction.outcome_probabilities}
        marginToRunnerUp={prediction.margin_to_runner_up}
        clarity={prediction.clarity}
        insufficient={insufficient}
      />

      {prediction.scoreline_band.length > 0 && (
        <div className="sqh-scoreline-row">
          <span className="sqh-scoreline-label">比分倾向</span>
          {prediction.scoreline_band.map(s => (
            <span className="sqh-scoreline-chip" key={s}>{s}</span>
          ))}
        </div>
      )}

      {prediction.drivers.length > 0 && (
        <p className="sqh-verdict-drivers">
          关键因子：{prediction.drivers.slice(0, 2).join('、')}
        </p>
      )}

      {prediction.sporttery_market && (
        <SportteryReference prediction={prediction} />
      )}
    </div>
  )
}

// ── ProbabilityBands ──

const PB_LABELS: Record<string, string> = { home_win: '主胜', draw: '平局', away_win: '客胜' }
const PB_COLORS: Record<string, string> = { home_win: '#1c4f3a', draw: '#c9a86a', away_win: '#6d725f' }

function ProbabilityBands({ probabilities, marginToRunnerUp, clarity, insufficient }: {
  probabilities: Record<'home_win' | 'draw' | 'away_win', number>
  marginToRunnerUp: number
  clarity: NonNullable<FootballOsintJob['prediction']>['clarity']
  insufficient: boolean
}) {
  const keys = ['home_win', 'draw', 'away_win'] as const
  const ranked = [...keys].sort((a, b) => probabilities[b] - probabilities[a])
  const lead = ranked[0]
  const leadSentence = insufficient
    ? null
    : clarity === 'clear'
      ? `首选${PB_LABELS[lead]} · 领先 ${Math.round(marginToRunnerUp * 100)} 个百分点`
      : `首选${PB_LABELS[lead]} · 优势不足，存在接近结果`

  return (
    <>
      {leadSentence && <p className="sqh-prob-lead">{leadSentence}</p>}
      <div className="sqh-prob-grid">
        {ranked.map(k => {
          const probability = Math.round(probabilities[k] * 100)
          return (
            <div className={`sqh-prob-cell${lead === k ? ' sqh-prob-cell--lead' : ''}`} data-lead={lead === k} key={k}>
              <span className="sqh-prob-label">{PB_LABELS[k]} {probability}%</span>
              <div className="sqh-prob-bar">
                <i style={{ width: `${probability}%`, background: PB_COLORS[k] }} />
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}

const HANDICAP_LABELS: Record<'home' | 'draw' | 'away', string> = {
  home: '让胜',
  draw: '让平',
  away: '让负',
}

function SportteryReference({ prediction }: { prediction: NonNullable<FootballOsintJob['prediction']> }) {
  const { sporttery_market: market, handicap_conclusion: conclusion } = prediction
  if (!market) return null

  const handicapLabel = market.home_handicap === null
    ? null
    : market.home_handicap >= 0
      ? `主队受让 +${market.home_handicap}`
      : `主队让 ${market.home_handicap}`

  return (
    <div className="sqh-sporttery-reference">
      <span className="sqh-sporttery-title">体彩官方盘口参考</span>
      {handicapLabel && <span>{handicapLabel}</span>}
      {conclusion && <span>{HANDICAP_LABELS[conclusion.outcome]} · {Math.round(conclusion.probability * 100)}%</span>}
    </div>
  )
}

// ── IntelCycle ──

const CYCLE_STATUS: Record<string, { cls: string; label: string }> = {
  completed: { cls: 'sqh-tag--ok', label: '完成' },
  partial: { cls: 'sqh-tag--warn', label: '部分' },
  skipped: { cls: 'sqh-tag--mute', label: '跳过' },
}

function IntelCycle({ stages }: { stages: FootballOsintJob['intelligence_cycle'] }) {
  return (
    <div className="sqh-cycle-grid">
      {stages.map((s, i) => {
        const meta = CYCLE_STATUS[s.status] || CYCLE_STATUS.skipped
        return (
          <div className={`sqh-cycle-step sqh-cycle-step--${s.status}`} key={s.name}>
            <h4>
              <span className="sqh-cycle-no">{i + 1}</span>
              {s.name}
              <span className={`sqh-tag ${meta.cls}`}>{meta.label}</span>
            </h4>
            <p>{s.summary}</p>
          </div>
        )
      })}
    </div>
  )
}

// ── FactorBars (diverging, centered) ──

function FactorBars({ factors }: { factors: FactorImpact[] }) {
  return (
    <div className="sqh-factors">
      {factors.map(f => {
        const pct = Math.max(Math.round(Math.abs(f.impact) * 50), f.enabled ? 3 : 0)
        return (
          <div className={`sqh-factor${!f.enabled ? ' sqh-factor--off' : ''}`} key={f.factor_id}>
            <div className="sqh-factor-name">
              <span>{f.label}</span>
              <span className="sqh-factor-group">{f.group}</span>
            </div>
            <div className="sqh-factor-track">
              <span className="sqh-factor-mid" />
              {f.enabled
                ? <span className={`sqh-factor-fill sqh-factor-fill--${f.direction}`}
                  style={{ width: `${pct}%` }} />
                : null}
            </div>
            <span className="sqh-factor-impact">
              {f.enabled
                ? `${f.direction === 'neutral' ? '±' : f.direction === 'home' ? '←' : '→'}${Math.abs(f.impact).toFixed(2)}`
                : '缺数据'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── EvidenceList ──

const SIDE_TAGS: Record<string, { cls: string; label: string }> = {
  home: { cls: 'sqh-tag--ok', label: '利主' },
  away: { cls: 'sqh-tag--gold', label: '利客' },
  neutral: { cls: 'sqh-tag--mute', label: '中性' },
  both: { cls: 'sqh-tag--info', label: '双向' },
}

function EvidenceList({ items }: { items: OsintEvidenceItem[] }) {
  if (items.length === 0) return <p className="sqh-empty">暂无证据条目。</p>
  return (
    <div className="sqh-evlist">
      {items.map(ev => {
        const side = SIDE_TAGS[ev.side] || SIDE_TAGS.neutral
        return (
          <div className="sqh-ev" key={ev.id}>
            <div className="sqh-ev-top">
              <span className="sqh-ev-source">{ev.source}</span>
              <span className={`sqh-tag ${side.cls}`}>{side.label}</span>
              <span className="sqh-ev-time">{ev.observed_at}</span>
            </div>
            <p className="sqh-ev-claim">{ev.claim}</p>
            <div className="sqh-ev-meters">
              <span className="sqh-ev-meter-label">可信</span>
              <span className="sqh-meter">
                <i style={{ width: `${(ev.confidence * 100).toFixed(0)}%` }} />
              </span>
              <span className="sqh-ev-meter-label">时效</span>
              <span className="sqh-meter sqh-meter--fresh">
                <i style={{ width: `${(ev.freshness * 100).toFixed(0)}%` }} />
              </span>
              {ev.url && (
                <a className="sqh-ev-url" href={ev.url} target="_blank" rel="noopener noreferrer">
                  {ev.url} ↗
                </a>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── FindingList ──

function FindingList({ items }: { items: IntelligenceFinding[] }) {
  if (items.length === 0) return <p className="sqh-empty">暂无该类条目。</p>
  return (
    <div>
      {items.map(f => (
        <div className="sqh-finding" key={f.id}>
          <span className={`sqh-finding-ic sqh-finding-ic--${f.finding_type}`}>
            {f.finding_type === 'confirmed' ? <CheckCircle size={14} weight="duotone" /> : <Scales size={13} weight="duotone" />}
          </span>
          <div>
            <p className="sqh-finding-text">{f.statement}</p>
            <div className="sqh-finding-meta">
              <ConfBadge level={f.confidence_level} />
              <span className="sqh-finding-src">{f.source_summary}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
