import {
  ArrowRight, Check, CheckCircle, Clock, Gauge, Graph, Key,
  Lightning, MagnifyingGlass, Scales, ShieldCheck, SpinnerGap, Stack,
} from '@phosphor-icons/react'
import { PLANS } from '../plans'

interface LandingPageProps {
  onEnter: () => void
  onRegister: () => void
  onLogin: () => void
}

const TRUST = [
  { val: '7', label: '类独立信源' },
  { val: 'L1–L4', label: '置信度评级' },
  { val: '5', label: '步情报循环' },
  { val: 'T-2h', label: '开赛前复扫' },
]

const STEPS = [
  { ic: <ShieldCheck size={22} weight="duotone" />, t: '核验主体', d: '锁定比赛、时间、场地，排除同名干扰，确定情报需求。' },
  { ic: <MagnifyingGlass size={22} weight="duotone" />, t: '多源采集', d: '官网、权威媒体、统计站、记者动态、气象——逐条命中、去重。' },
  { ic: <Graph size={22} weight="duotone" />, t: '因子加权', d: '翻译结构化后按时效与可信度打分，贝叶斯更新方向概率。' },
  { ic: <Gauge size={22} weight="duotone" />, t: '出具研判', d: '给出方向、概率区间与 L1–L4 置信度，证据链全程可查。' },
]

const FEATURES = [
  { ic: <Stack size={22} weight="duotone" />, t: '实时情报循环', d: '研判过程全程可见：信源逐条点亮，各阶段进度透明，而不是一个黑盒结果。' },
  { ic: <Scales size={22} weight="duotone" />, t: '证据链可追溯', d: '每条结论标注来源、时效与可信度；区分「确认事实」与「研判推断」。' },
  { ic: <ShieldCheck size={22} weight="duotone" />, t: '诚实的不确定性', d: 'L1–L4 置信度分级，关键数据缺失时直接说「信息不足」，不强行给倾向。' },
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

      <ShowcaseMock onEnter={onEnter} />

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

// Static product preview shown in the hero — a glimpse of the 研判台.
const MOCK_STEPS: { label: string; state: 'done' | 'active' | 'todo' }[] = [
  { label: '核验', state: 'done' },
  { label: '采集', state: 'done' },
  { label: '归一', state: 'done' },
  { label: '打分', state: 'active' },
  { label: '研判', state: 'todo' },
]

const MOCK_PROB: [string, number][] = [['主胜', 48], ['平局', 27], ['客胜', 25]]

function ShowcaseMock({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="sqh-showcase" onClick={onEnter} role="button" tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onEnter() }}>
      <div className="sqh-showcase-bar">
        <i /><i /><i />
        <span className="mono">qiuhua.app / 研判台</span>
      </div>
      <div className="sqh-showcase-body">
        <div className="sqh-showcase-card">
          <div className="sqh-showcase-league">英超 · 第32轮</div>
          <div className="sqh-showcase-teams">
            <span>阿森纳</span><em>VS</em><span>曼城</span>
          </div>
          <span className="sqh-cbadge sqh-cbadge--L2" style={{ marginTop: 14 }}>L2 · 高可信</span>
          <div className="sqh-showcase-prob">
            {MOCK_PROB.map(([l, v]) => (
              <div key={l}>
                <span>{l}</span>
                <b className="mono">{v}%</b>
              </div>
            ))}
          </div>
        </div>
        <div className="sqh-showcase-steps">
          {MOCK_STEPS.map((s, i) => (
            <div className={`sqh-showcase-step sqh-showcase-step--${s.state}`} key={s.label}>
              <span className="sqh-showcase-bead">
                {s.state === 'done' ? <CheckCircle size={13} weight="fill" />
                  : s.state === 'active' ? <SpinnerGap size={13} weight="bold" className="sqh-phase-spin" />
                  : <span className="mono">{i + 1}</span>}
              </span>
              <span>{s.label}</span>
              {s.state === 'done' && <span className="sqh-tag sqh-tag--ok">命中</span>}
            </div>
          ))}
          <div className="sqh-showcase-note">
            <ShieldCheck size={14} weight="duotone" />主队首发完整 · 客队中卫停赛（双源确认）
          </div>
        </div>
      </div>
    </div>
  )
}
