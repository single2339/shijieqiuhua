// landing-redesign.jsx — full landing-page layout, redesigned to give the
// prediction track record a prominent, full-bleed proof section right after
// the hero showcase (previously a small collapsed link buried in the hero).
// Everything else (steps / features / honesty / pricing / footer) keeps the
// existing copy and structure from views.jsx's Landing — only re-ordered to
// make room for the new section.

function LandingRedesign({ onEnter, onAuth }) {
  return (
    <div className="land">
      <nav className="land-nav">
        <div className="brand" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          <div className="brand-mark">世</div>
          <div><div className="brand-name">世界球花</div><div className="brand-sub">足球情报研判</div></div>
        </div>
        <div className="grow" />
        <nav className="topnav">
          <a href="#record">公开战绩</a>
          <a href="#how">方法论</a>
          <a href="#feat">能力</a>
          <a href="#price">价格</a>
        </nav>
        <button className="btn btn-quiet btn-sm" onClick={() => onAuth("login")}>登录</button>
        <button className="btn btn-primary btn-sm" onClick={() => onAuth("register")}>邀请码注册</button>
      </nav>

      <header className="land-wrap hero-land">
        <span className="eyebrow"><IconShieldCheck size={15} />缺数据时如实说明，不编造倾向</span>
        <h1 className="display">把一场比赛，<br /><span className="accent">当成一次情报研判</span></h1>
        <p className="lead">
          多源采集、交叉验证、因子加权——世界球花用 OSINT 情报循环为每场比赛生成带置信度的结论，
          每一条判断都看得到证据来源，缺数据就明说。
        </p>
        <div className="hero-cta">
          <button className="btn btn-primary btn-lg" onClick={onEnter}>进入研判台 <IconArrowRight size={17} /></button>
          <button className="btn btn-ghost btn-lg" onClick={() => onAuth("register")}><IconKey size={16} />用邀请码注册</button>
        </div>
        <div className="trust-row">
          <div className="t"><b>7</b><span>类独立信源</span></div>
          <div className="t"><b>L1–L4</b><span>置信度评级</span></div>
          <div className="t"><b>5</b><span>步情报循环</span></div>
          <div className="t"><b>T-2h</b><span>开赛前复扫</span></div>
        </div>
      </header>

      {/* ── public track record — promoted to its own full-bleed proof section ── */}
      <TrackRecordProof data={TRACK_RECORD} />

      {/* how it works */}
      <section className="section land-wrap" id="how">
        <div className="section-kicker">情报循环</div>
        <h2 className="section-title">不是预测，是研判</h2>
        <p className="section-sub">同一套被情报分析师使用的方法论：收集 → 加工 → 开发 → 生产，每一步都可追溯。</p>
        <div className="steps">
          {[
            { ic: <IconShieldCheck size={20} />, no: "01", t: "核验主体", d: "锁定比赛、时间、场地，排除同名干扰，确定情报需求。" },
            { ic: <IconSearch size={20} />, no: "02", t: "多源采集", d: "官网、权威媒体、统计站、记者动态、气象——逐条命中、去重。" },
            { ic: <IconGraph size={20} />, no: "03", t: "因子加权", d: "翻译结构化后按时效与可信度打分，贝叶斯更新方向概率。" },
            { ic: <IconGauge size={20} />, no: "04", t: "出具研判", d: "给出方向、概率区间与 L1–L4 置信度，证据链全程可查。" },
          ].map(s => (
            <div className="step" key={s.no}>
              <div className="feat-ic">{s.ic}</div>
              <div className="step-no" style={{ marginTop: 12 }}>{s.no}</div>
              <h3>{s.t}</h3><p>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* features */}
      <section className="section land-wrap" id="feat">
        <div className="section-kicker">产品能力</div>
        <h2 className="section-title">看得见证据的结论</h2>
        <div className="feat-grid">
          {[
            { ic: <IconLayers size={22} />, t: "实时情报循环", d: "研判过程全程可见：信源逐条点亮，各阶段进度透明，而不是一个黑盒结果。" },
            { ic: <IconScale size={22} />, t: "证据链可追溯", d: "每条结论标注来源、时效与可信度；区分「确认事实」与「研判推断」。" },
            { ic: <IconShieldCheck size={22} />, t: "诚实的不确定性", d: "L1–L4 置信度分级，关键数据缺失时直接说「信息不足」，不强行给倾向。" },
            { ic: <IconGraph size={22} />, t: "因子权重透明", d: "阵容、状态、历史、环境等因子的方向与权重一目了然，可看到贝叶斯轨迹。" },
            { ic: <IconClock size={22} />, t: "开赛前自动复扫", d: "首发与伤情常在临场释放——我们在开赛前 2 小时再扫一遍并提醒你。" },
            { ic: <IconBolt size={22} />, t: "结构化问答", d: "比分、角球、红黄牌、球员、风险——针对量化问题给出可核对的数值预测。" },
          ].map(f => (
            <div className="feat" key={f.t}>
              <div className="feat-ic">{f.ic}</div>
              <h3>{f.t}</h3><p>{f.d}</p>
            </div>
          ))}
        </div>

        <div className="honesty">
          <div className="q">"这场缺关键数据，我们没编。"</div>
          <p className="a">大多数预测产品永远给你一个看似笃定的答案。我们不同：当证据不足以支撑方向时，我们如实告知，并安排复扫——可靠，比好看更重要。</p>
        </div>
      </section>

      {/* pricing */}
      <section className="section land-wrap" id="price">
        <div className="section-kicker">价格</div>
        <h2 className="section-title">按需选择</h2>
        <p className="section-sub">免费会员每日 1 次完整研判；情报通解锁无限研判与全部深度视图。</p>
        <div className="pricing">
          {PLANS.map(p => (
            <div className="plan" data-feature={p.feature} key={p.id}>
              {p.feature && <span className="plan-tag">最受欢迎</span>}
              <h3>{p.name}</h3>
              <div className="price"><span>¥</span><b>{p.price}</b><span>{p.unit}</span></div>
              <ul>{p.items.map(it => <li key={it}><IconCheck size={15} />{it}</li>)}</ul>
              <div className="grow" />
              <button className={`btn ${p.feature ? "btn-gold" : "btn-ghost"} btn-block`}
                onClick={p.id === "guest" ? onEnter : () => onAuth("register")}>{p.cta}</button>
            </div>
          ))}
        </div>
      </section>

      <footer className="land-foot">
        <div className="land-wrap" style={{ padding: 0 }}>
          <div className="disc">
            <strong>免责声明：</strong>世界球花提供的是基于公开信息的情报研判与不确定性评估，
            <strong>不构成任何投注或博彩建议</strong>。所有结论均附证据来源，请理性看待并自行判断。
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <span>© 2026 世界球花 · 足球情报研判</span>
            <span style={{ display: "flex", gap: 16 }}>
              <a href="#" style={{ color: "var(--gold-deep)" }}>用户协议</a>
              <a href="#" style={{ color: "var(--gold-deep)" }}>隐私政策</a>
              <a href="#" style={{ color: "var(--gold-deep)" }}>联系我们</a>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function LandingRedesignApp() {
  const [authOpen, setAuthOpen] = React.useState(false);
  return (
    <React.Fragment>
      <LandingRedesign onEnter={() => alert("进入研判台（原型不含完整研判台流程）")} onAuth={() => setAuthOpen(true)} />
      {authOpen && (
        <div className="modal-veil" onClick={() => setAuthOpen(false)}>
          <div className="modal" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
            <div className="modal-hd"><b>登录 / 注册</b><button className="x-btn" onClick={() => setAuthOpen(false)}><IconX size={16} /></button></div>
            <div className="modal-bd" style={{ color: "var(--ink-soft)", fontSize: 13.5 }}>原型不含完整鉴权流程，详见生产 AuthScreen 组件。</div>
          </div>
        </div>
      )}
    </React.Fragment>
  );
}

const rootEl = document.getElementById("root");
ReactDOM.createRoot(rootEl).render(<LandingRedesignApp />);
