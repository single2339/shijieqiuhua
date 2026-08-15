// views.jsx — landing page + auth screen (presentational, drive callbacks up).
const { useState: useS } = React;

// ───────────────────────── landing ─────────────────────────
function Landing({ onEnter, onAuth }) {
  return (
    <div className="land">
      <nav className="land-nav">
        <div className="brand" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          <div className="brand-mark">世</div>
          <div><div className="brand-name">世界球花</div><div className="brand-sub">足球情报研判</div></div>
        </div>
        <div className="grow" />
        <nav className="topnav">
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

      <div className="land-wrap"><ShowcaseMock onEnter={onEnter} /></div>

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
          <div className="q">“这场缺关键数据，我们没编。”</div>
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

// a small static mock of the product, used as the hero showcase
function ShowcaseMock({ onEnter }) {
  return (
    <div className="land-showcase" onClick={onEnter} style={{ cursor: "pointer" }}>
      <div className="showcase-bar"><i /><i /><i /><span style={{ marginLeft: 8, fontSize: 12, color: "var(--ink-faint)" }} className="mono">qiuhua.app / 研判台</span></div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 12, padding: 8 }}>
        <div className="hero" style={{ padding: 18, borderRadius: 16 }}>
          <div className="hero-meta"><span>英超 · 第32轮</span></div>
          <div className="hero-teams" style={{ marginTop: 10 }}>
            <span className="hero-team" style={{ fontSize: 24 }}>阿森纳</span>
            <span className="hero-vs">VS</span>
            <span className="hero-team" style={{ fontSize: 24 }}>曼城</span>
          </div>
          <div style={{ marginTop: 16 }}><span className="conf conf-L2">L2 · 高可信</span></div>
          <div className="prob" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 7, marginTop: 14 }}>
            {[["主胜", 48, "var(--brand-600)"], ["平局", 27, "var(--gold-deep)"], ["客胜", 25, "var(--ink-soft)"]].map(([l, v, c]) => (
              <div key={l} style={{ background: "rgba(248,241,223,.1)", borderRadius: 9, padding: 8 }}>
                <div style={{ fontSize: 10, color: "rgba(248,241,223,.7)" }}>{l}</div>
                <div className="mono" style={{ fontSize: 17, fontWeight: 700, color: "var(--on-brand)" }}>{v}%</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[["核验", "done"], ["采集", "done"], ["归一", "done"], ["打分", "active"], ["研判", "todo"]].map(([n, st], i) => (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", border: "1px solid var(--line)", borderRadius: 12, background: st === "todo" ? "var(--surface-2)" : "var(--surface)" }}>
              <span className="phase-bead" style={{ width: 22, height: 22, background: st === "done" ? "var(--brand)" : st === "active" ? "var(--surface)" : "var(--surface-3)", color: st === "done" ? "var(--on-brand)" : "var(--brand)", borderColor: st === "todo" ? "var(--line-2)" : "var(--brand-600)" }}>
                {st === "done" ? <IconCheck size={12} /> : st === "active" ? <span className="spin" style={{ width: 11, height: 11 }} /> : <span className="mono" style={{ fontSize: 10 }}>{i + 1}</span>}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{n}</span>
              {st === "done" && <span className="tag tag-green" style={{ marginLeft: "auto" }}>命中</span>}
            </div>
          ))}
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--ink-soft)", marginTop: 2 }}>
            <IconShieldCheck size={14} style={{ color: "var(--brand-600)" }} />主队首发完整 · 客队中卫停赛（双源确认）
          </div>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── auth ─────────────────────────
function AuthScreen({ mode, setMode, onAuthed, onBack }) {
  const [name, setName] = useS("");
  const [pass, setPass] = useS("");
  const [email, setEmail] = useS("");
  const [invite, setInvite] = useS("");
  const [err, setErr] = useS("");

  function submit() {
    if (!name || !pass) { setErr("请填写用户名和密码"); return; }
    if (mode === "register" && !invite) { setErr("注册需要邀请码（试试 QIUHUA-2026）"); return; }
    setErr("");
    onAuthed(name);
  }

  return (
    <div className="auth-screen">
      <aside className="auth-aside">
        <div className="brand" onClick={onBack} style={{ cursor: "pointer" }}>
          <div className="brand-mark">世</div>
          <div><div className="brand-name" style={{ color: "var(--on-brand)" }}>世界球花</div>
            <div className="brand-sub" style={{ color: "rgba(248,241,223,.6)" }}>足球情报研判</div></div>
        </div>
        <div>
          <div className="auth-quote">每一条结论，<br />都看得见证据来源。</div>
          <div className="auth-feat">
            {[
              { ic: <IconLayers size={17} />, t: "实时情报循环", d: "信源逐条点亮，研判过程全透明。" },
              { ic: <IconShieldCheck size={17} />, t: "诚实的不确定性", d: "缺数据时如实说「信息不足」。" },
              { ic: <IconGauge size={17} />, t: "L1–L4 置信度", d: "每个结论都带可靠性评级。" },
            ].map(f => (
              <div className="f" key={f.t}>
                <span className="fi">{f.ic}</span>
                <div><b>{f.t}</b><span>{f.d}</span></div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ fontSize: 12, color: "rgba(248,241,223,.55)" }}>不构成投注建议 · 理性看待研判结论</div>
      </aside>

      <main className="auth-main">
        <div className="auth-form">
          <button className="btn btn-quiet btn-sm" onClick={onBack} style={{ marginLeft: -12 }}>← 返回首页</button>
          <h2 style={{ fontSize: 24, fontWeight: 800, marginTop: 12, letterSpacing: "-.02em" }}>
            {mode === "login" ? "欢迎回来" : "创建账号"}
          </h2>
          <p style={{ color: "var(--ink-soft)", fontSize: 13.5, marginTop: 6 }}>
            {mode === "login" ? "登录后继续你的情报研判。" : "注册即享每日 1 次完整研判。"}
          </p>

          <div className="auth-tabs">
            <button className="auth-tab" data-on={mode === "login"} onClick={() => { setMode("login"); setErr(""); }}>登录</button>
            <button className="auth-tab" data-on={mode === "register"} onClick={() => { setMode("register"); setErr(""); }}>注册</button>
          </div>

          <div className="auth-fields">
            <div className="field"><label>用户名</label>
              <input className="input" value={name} placeholder="你的用户名" onChange={e => setName(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") submit(); }} /></div>
            <div className="field"><label>密码</label>
              <input className="input" type="password" value={pass} placeholder="••••••••" onChange={e => setPass(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") submit(); }} /></div>
            {mode === "register" && (
              <>
                <div className="field"><label>邮箱（选填）</label>
                  <input className="input" value={email} placeholder="name@example.com" onChange={e => setEmail(e.target.value)} /></div>
                <div className="field"><label>邀请码</label>
                  <input className="input" value={invite} placeholder="例如 QIUHUA-2026" onChange={e => setInvite(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") submit(); }} /></div>
              </>
            )}
            {err && <div className="auth-err">{err}</div>}
            <button className="btn btn-primary btn-lg btn-block" onClick={submit}>
              {mode === "login" ? "登录" : "注册并进入"} <IconArrowRight size={16} />
            </button>
          </div>

          <p style={{ textAlign: "center", fontSize: 12.5, color: "var(--ink-soft)", marginTop: 16 }}>
            {mode === "login" ? "还没有账号？" : "已有账号？"}
            <a onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}
              style={{ color: "var(--brand-600)", fontWeight: 600, cursor: "pointer", marginLeft: 4 }}>
              {mode === "login" ? "用邀请码注册" : "去登录"}
            </a>
          </p>
        </div>
      </main>
    </div>
  );
}

Object.assign(window, { Landing, AuthScreen, ShowcaseMock });
