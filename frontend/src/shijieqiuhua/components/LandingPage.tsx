import {
  ArrowRight, Check, Clock, Gauge, Graph, Key,
  Lightning, MagnifyingGlass, Scales, ShieldCheck, Stack, X,
} from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { fetchTrackRecord } from '../api'
import { PLANS } from '../plans'
import type { TrackRecordStats } from '../types'

interface LandingPageProps {
  onEnter: () => void
  onRegister: () => void
  onLogin: () => void
}

const TRUST = [
  { val: '7', label: '类独立信源' },
  { val: '4', label: '档可信度分级' },
  { val: '5', label: '步情报循环' },
  { val: 'T-2h', label: '开赛前复扫' },
]

export function formatTrackRecordSummary(stats: TrackRecordStats): string | null {
  if (stats.lean_accuracy === undefined || stats.scoreline_accuracy === undefined) return null
  const leanPct = Math.round(stats.lean_accuracy * 100)
  const scorePct = Math.round(stats.scoreline_accuracy * 100)
  return `近 ${stats.settled} 场比赛 · 方向命中率 ${leanPct}% · 比分命中率 ${scorePct}%`
}

const LEAN_LABEL: Record<string, string> = { home: '主胜', away: '主负', draw: '平局' }

// Public track-record proof section — promoted from a collapsed hero link to
// its own full-bleed section so it can carry real conversion weight.
function TrackRecordProof() {
  const [stats, setStats] = useState<TrackRecordStats | null>(null)

  useEffect(() => {
    fetchTrackRecord().then(setStats).catch(() => {})
  }, [])

  if (!stats) return null
  // formatTrackRecordSummary doubles as the "sample big enough to show" gate.
  const gate = formatTrackRecordSummary(stats)
  if (!gate || !stats.recent || stats.lean_accuracy === undefined || stats.scoreline_accuracy === undefined) return null

  const leanPct = Math.round(stats.lean_accuracy * 100)
  const scorePct = Math.round(stats.scoreline_accuracy * 100)

  return (
    <section className="sqh-proof" id="record">
      <div className="sqh-proof-inner">
        <div className="sqh-proof-head">
          <div className="sqh-proof-kicker"><ShieldCheck size={14} weight="duotone" />公开战绩 · 非营销话术</div>
          <h2 className="sqh-proof-title">每一条判断，事后都对得上账</h2>
          <p className="sqh-proof-sub">
            我们记录每一场给出明确方向的研判，比赛结束后用第三方数据源核对实际结果。
            模糊倾向与「信息不足」不计入命中率统计——拒绝靠宽松口径粉饰战绩。
          </p>
        </div>

        <div className="sqh-proof-stats">
          <div className="sqh-proof-stat"><b className="mono">{stats.settled}</b><span>场已结算判断</span></div>
          <div className="sqh-proof-stat sqh-proof-stat--accent"><b className="mono">{leanPct}%</b><span>方向命中率</span></div>
          <div className="sqh-proof-stat"><b className="mono">{scorePct}%</b><span>比分区间命中率</span></div>
        </div>

        <div className="sqh-proof-rule">
          <Scales size={18} weight="duotone" />
          <p>只统计 <b>主胜 / 主负 / 平局</b> 这类明确方向的判断；遇到模糊倾向或证据不足时我们直接说「信息不足」——这部分不参与命中率计算，也不会拉低或美化数字。</p>
        </div>

        <div className="sqh-proof-cards-head"><h3>最近战绩</h3></div>
        <div className="sqh-proof-cards">
          {stats.recent.map((r, i) => (
            <div className="sqh-proof-card" key={i}>
              <div className="sqh-proof-card-top">
                <span className="sqh-proof-card-date mono">{r.kickoff_at.slice(0, 5)}</span>
              </div>
              <div className="sqh-proof-card-teams">{r.home_team}<span className="vs">vs</span>{r.away_team}</div>
              <div className="sqh-proof-card-row"><span className="lab">研判</span><span>{LEAN_LABEL[r.predicted_lean] ?? r.predicted_lean} · {r.predicted_scoreline_band.join('/')}</span></div>
              <div className="sqh-proof-card-row"><span className="lab">实际比分</span><span className="mono sqh-proof-card-score">{r.actual_home_score}-{r.actual_away_score}</span></div>
              <div className="sqh-proof-card-badge" data-hit={r.lean_correct}>
                {r.lean_correct ? <Check size={13} weight="bold" /> : <X size={13} weight="bold" />}
                {r.lean_correct ? '命中' : '未中'}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

const STEPS = [
  { ic: <ShieldCheck size={22} weight="duotone" />, t: '核验主体', d: '锁定比赛、时间、场地，排除同名干扰，确定情报需求。' },
  { ic: <MagnifyingGlass size={22} weight="duotone" />, t: '多源采集', d: '官网、权威媒体、统计站、记者动态、气象——逐条命中、去重。' },
  { ic: <Graph size={22} weight="duotone" />, t: '因子加权', d: '翻译结构化后按时效与可信度打分，贝叶斯更新方向概率。' },
  { ic: <Gauge size={22} weight="duotone" />, t: '出具研判', d: '给出方向、概率区间与可信度分级，证据链全程可查。' },
]

const FEATURES = [
  { ic: <Stack size={22} weight="duotone" />, t: '实时情报循环', d: '研判过程全程可见：信源逐条点亮，各阶段进度透明，而不是一个黑盒结果。' },
  { ic: <Scales size={22} weight="duotone" />, t: '证据链可追溯', d: '每条结论标注来源、时效与可信度；区分「确认事实」与「研判推断」。' },
  { ic: <ShieldCheck size={22} weight="duotone" />, t: '诚实的不确定性', d: '确认、高可信、中可信、推测四档分级，关键数据缺失时直接说「信息不足」，不强行给倾向。' },
  { ic: <Graph size={22} weight="duotone" />, t: '因子权重透明', d: '阵容、状态、历史、环境等因子的方向与权重一目了然，可看到贝叶斯轨迹。' },
  { ic: <Clock size={22} weight="duotone" />, t: '开赛前自动复扫', d: '首发与伤情常在临场释放——我们在开赛前 2 小时再扫一遍并提醒你。' },
  { ic: <Lightning size={22} weight="duotone" />, t: '结构化问答', d: '比分、角球、红黄牌、球员、风险——针对量化问题给出可核对的数值预测。' },
]

export default function LandingPage({ onEnter, onRegister, onLogin }: LandingPageProps) {
  return (
    <div className="sqh-land">
      {/* nav */}
      <nav className="sqh-land-nav">
        <div className="sqh-brand">
          <div className="sqh-mark">世</div>
          <div><h1>世界球花</h1><p>足球情报研判</p></div>
        </div>
        <div className="grow" />
        <a href="#how" className="sqh-land-link">方法论</a>
        <a href="#feat" className="sqh-land-link">能力</a>
        <a href="#price" className="sqh-land-link">价格</a>
        <button className="btn btn-quiet btn-sm" onClick={onLogin}>登录</button>
        <button className="btn btn-primary btn-sm" onClick={onRegister} style={{ marginLeft: 8 }}>
          <Key size={15} />邀请码注册
        </button>
      </nav>

      {/* hero */}
      <header className="sqh-land-hero">
        <span className="sqh-land-badge">
          <ShieldCheck size={16} weight="duotone" />缺数据时如实说明，不编造倾向
        </span>
        <h2 className="sqh-land-display">
          把一场比赛，<br /><span className="sqh-land-accent">当成一次情报研判</span>
        </h2>
        <p className="sqh-land-lead">
          多源采集、交叉验证、因子加权——世界球花用 OSINT 情报循环为每场比赛生成带置信度的结论，
          每一条判断都看得到证据来源，缺数据就明说。
        </p>
        <div className="sqh-land-cta">
          <button className="btn btn-primary btn-lg" onClick={onEnter}>
            进入研判台 <ArrowRight size={17} weight="bold" />
          </button>
          <button className="btn btn-gold btn-lg" onClick={onRegister}>
            <Key size={16} />用邀请码注册
          </button>
        </div>
        <div className="sqh-land-trust">
          {TRUST.map(t => (
            <div className="sqh-land-stat" key={t.label}>
              <b className="mono">{t.val}</b>
              <span>{t.label}</span>
            </div>
          ))}
        </div>
      </header>

      <TrackRecordProof />

      {/* how it works */}
      <section className="sqh-land-section" id="how">
        <div className="sqh-land-kicker">情报循环</div>
        <h2 className="sqh-land-title">不是预测，是研判</h2>
        <p className="sqh-land-sub">
          同一套被情报分析师使用的方法论：收集 → 加工 → 开发 → 生产，每一步都可追溯。
        </p>
        <div className="sqh-land-steps">
          {STEPS.map((s, i) => (
            <div className="sqh-land-step" key={s.t}>
              <div className="sqh-feat-ic">{s.ic}</div>
              <div className="mono sqh-land-step-no">0{i + 1}</div>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* features */}
      <section className="sqh-land-section" id="feat">
        <div className="sqh-land-kicker">产品能力</div>
        <h2 className="sqh-land-title">看得见证据的结论</h2>
        <div className="sqh-land-features">
          {FEATURES.map(f => (
            <div className="sqh-land-feat" key={f.t}>
              <div className="sqh-feat-ic">{f.ic}</div>
              <h3>{f.t}</h3>
              <p>{f.d}</p>
            </div>
          ))}
        </div>

        <div className="sqh-land-honesty">
          <div className="sqh-land-honesty-q">“这场缺关键数据，我们没编。”</div>
          <p className="sqh-land-honesty-a">
            大多数预测产品永远给你一个看似笃定的答案。我们不同：当证据不足以支撑方向时，我们如实告知，并安排复扫——可靠，比好看更重要。
          </p>
        </div>
      </section>

      {/* pricing */}
      <section className="sqh-land-section" id="price">
        <div className="sqh-land-kicker">价格</div>
        <h2 className="sqh-land-title">按需选择</h2>
        <p className="sqh-land-sub">
          免费会员每日 1 次完整研判；情报通解锁无限研判与全部深度视图。
        </p>
        <div className="sqh-land-pricing">
          {PLANS.map(p => (
            <div className={`sqh-land-plan${p.featured ? ' sqh-land-plan--feat' : ''}`} key={p.id}>
              {p.featured && <span className="sqh-land-plan-tag">最受欢迎</span>}
              <h3>{p.name}</h3>
              <div className="sqh-land-price">
                <span>¥</span><b>{p.price}</b><span>{p.unit}</span>
              </div>
              <ul className="sqh-land-plan-items">
                {p.items.map(it => <li key={it}><Check size={14} weight="bold" />{it}</li>)}
              </ul>
              <button className={`btn ${p.featured ? 'btn-gold' : 'btn-ghost'} btn-block`}
                onClick={p.id === 'guest' ? onEnter : onRegister}>
                {p.id === 'guest' ? '直接逛逛' : p.id === 'free' ? '用邀请码注册' : '开通情报通'}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* footer */}
      <footer className="sqh-land-foot">
        <div className="sqh-land-disc">
          <strong>免责声明：</strong>世界球花提供的是基于公开信息的情报研判与不确定性评估，
          <strong>不构成任何投注或博彩建议</strong>。所有结论均附证据来源，请理性看待并自行判断。
        </div>
        <div className="sqh-land-foot-row">
          <span>© 2026 世界球花 · 足球情报研判</span>
          <span className="sqh-land-foot-links">
            <a href="/terms.html">用户协议</a>
            <a href="/privacy.html">隐私政策</a>
            <a href="mailto:hello@qiuhua.app">联系我们</a>
          </span>
        </div>
      </footer>
    </div>
  )
}
