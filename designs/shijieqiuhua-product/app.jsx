// app.jsx — orchestrator: landing → auth → workspace, analysis runner,
// paywall, account, admin, history. Owns all shared state.
const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ───────────────────────── analysis runner hook ─────────────────────────
// Drives the 5-phase tracker with streamed source feed, then resolves a result.
function useAnalysisRunner() {
  const [run, setRun] = useState({ status: "idle", phaseIdx: 0, progress: 0, feed: [], result: null });
  const timers = useRef([]);
  const clear = () => { timers.current.forEach(clearTimeout); timers.current = []; };

  const start = useCallback((match, question) => {
    clear();
    setRun({ status: "running", phaseIdx: 0, progress: 6, feed: [], result: null });
    const sched = (at, fn) => timers.current.push(setTimeout(fn, at));

    sched(500, () => setRun(r => ({ ...r, progress: 16 })));
    sched(900, () => setRun(r => ({ ...r, phaseIdx: 1, progress: 24 })));

    // stream sources during "collect"
    SOURCE_POOL.forEach((s, i) => {
      sched(1100 + i * 360, () => setRun(r => ({
        ...r,
        feed: [...r.feed, { ...s, status: i === SOURCE_POOL.length - 1 ? "skipped" : "ok" }],
        progress: Math.min(24 + (i + 1) * 6, 56),
      })));
    });

    const afterCollect = 1100 + SOURCE_POOL.length * 360 + 250;
    sched(afterCollect, () => setRun(r => ({ ...r, phaseIdx: 2, progress: 70 })));
    sched(afterCollect + 700, () => setRun(r => ({ ...r, phaseIdx: 3, progress: 85 })));
    sched(afterCollect + 1400, () => setRun(r => ({ ...r, phaseIdx: 4, progress: 95 })));
    sched(afterCollect + 2100, () => setRun(r => ({
      status: "done", phaseIdx: 5, progress: 100, feed: r.feed, result: buildAnalysis(match, question),
    })));
  }, []);

  const reset = useCallback(() => { clear(); setRun({ status: "idle", phaseIdx: 0, progress: 0, feed: [], result: null }); }, []);
  useEffect(() => clear, []);
  return { run, start, reset };
}

// ───────────────────────── root ─────────────────────────
function App() {
  const [view, setView] = useState("landing");      // landing | auth | app
  const [user, setUser] = useState(null);            // { name, tier, quota }
  const [authMode, setAuthMode] = useState("register");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(null);          // 'paywall' | 'admin' | null
  const [history, setHistory] = useState([]);

  const [selectedId, setSelectedId] = useState(FIXTURES[0].id);
  const [question, setQuestion] = useState(QUESTION_PRESETS[0].prompt);
  const { run, start, reset } = useAnalysisRunner();

  const match = useMemo(() => FIXTURES.find(f => f.id === selectedId) || FIXTURES[0], [selectedId]);
  const tier = user ? user.tier : "guest";

  const flash = useCallback((m) => { setToast(m); setTimeout(() => setToast(""), 2400); }, []);

  // demo-only: switch identity so a reviewer can see every gated state
  const setTier = (t) => {
    if (t === "guest") { setUser(null); }
    else setUser(u => ({ name: u?.name || "qiuhua_demo", tier: t, quota: t === "paid" ? Infinity : 1, role: u?.role }));
    flash(t === "guest" ? "已切到访客视角" : t === "paid" ? "已切到「情报通」视角" : "已切到免费会员视角");
  };

  function handleAuthed(name) {
    setUser({ name, tier: "free", quota: 1, role: name === "admin" ? "admin" : "user" });
    setView("app");
    flash(`欢迎，${name}`);
  }

  const canDeep = tier === "paid" || (tier === "free" && (user?.quota ?? 0) > 0);

  function ask(prompt) {
    const q = prompt ?? question;
    setQuestion(q);
    if (tier === "guest") { start(match, q); return; }      // guest gets preview, deep veiled
    if (tier === "free" && (user?.quota ?? 0) <= 0) { setModal("paywall"); return; }
    start(match, q);
    if (tier === "free") setUser(u => ({ ...u, quota: Math.max(0, u.quota - 1) }));
  }

  // log to history when a run completes
  useEffect(() => {
    if (run.status === "done" && run.result) {
      setHistory(h => [{ q: question, match: `${match.home} vs ${match.away}`,
        level: run.result.confidence.level, at: "刚刚" }, ...h].slice(0, 6));
    }
  }, [run.status]); // eslint-disable-line

  function pickFixture(id) { setSelectedId(id); reset(); }

  if (view === "landing")
    return <><Landing onEnter={() => setView("app")} onAuth={(m) => { setAuthMode(m); setView("auth"); }} /><Toast msg={toast} /></>;
  if (view === "auth")
    return <><AuthScreen mode={authMode} setMode={setAuthMode} onAuthed={handleAuthed} onBack={() => setView("landing")} /><Toast msg={toast} /></>;

  return (
    <div className="app">
      <Topbar view={view} user={user} tier={tier} onHome={() => setView("landing")}
        onLogin={() => { setAuthMode("login"); setView("auth"); }}
        onLogout={() => { setUser(null); reset(); flash("已退出"); }}
        setTier={setTier} onAdmin={() => setModal("admin")} />

      <div className="workspace">
        <div className="col col-left">
          <FixturesRail selectedId={selectedId} onPick={pickFixture} />
        </div>

        <div className="col center col-scroll">
          <MatchHero match={match} />
          <AskBox match={match} question={question} setQuestion={setQuestion}
            onAsk={ask} running={run.status === "running"} tier={tier} />

          {run.status === "running" && <PhaseTracker phaseIdx={run.phaseIdx} progress={run.progress} feed={run.feed} />}

          {run.status === "done" && run.result && (
            <ReportView result={run.result} canDeep={canDeep} tier={tier}
              onUnlock={() => setModal("paywall")} onAuth={() => { setAuthMode("register"); setView("auth"); }} />
          )}

          {run.status === "idle" && <IdleHint tier={tier} />}
        </div>

        <div className="col col-right col-scroll">
          <AccountPanel user={user} tier={tier} history={history}
            onLogin={() => { setAuthMode("login"); setView("auth"); }}
            onRegister={() => { setAuthMode("register"); setView("auth"); }}
            onUnlock={() => setModal("paywall")} onAdmin={() => setModal("admin")} />
        </div>
      </div>

      {modal === "paywall" && <PaywallModal onClose={() => setModal(null)}
        onPaid={() => { setUser(u => ({ ...(u || { name: "qiuhua_demo", role: "user" }), tier: "paid", quota: Infinity })); setModal(null); flash("已解锁「情报通」，尽情研判"); }} />}
      {modal === "admin" && <AdminModal onClose={() => setModal(null)} />}
      <Toast msg={toast} />
    </div>
  );
}

// ───────────────────────── topbar ─────────────────────────
function Topbar({ user, tier, onHome, onLogin, onLogout, setTier, onAdmin }) {
  return (
    <div className="topbar">
      <div className="brand" onClick={onHome}>
        <div className="brand-mark">世</div>
        <div>
          <div className="brand-name">世界球花</div>
          <div className="brand-sub">足球情报研判</div>
        </div>
      </div>

      <nav className="topnav" style={{ marginLeft: 8 }}>
        <a data-on="true">研判台</a>
        <a onClick={onHome} style={{ cursor: "pointer" }}>方法论</a>
      </nav>

      <div className="grow" />

      {/* demo identity switch */}
      <div className="auth-tabs" style={{ margin: 0, height: 36, padding: 3, gap: 2 }}>
        {["guest", "free", "paid"].map(t => (
          <button key={t} className="auth-tab" data-on={tier === t} style={{ height: 30, fontSize: 12.5, padding: "0 12px" }}
            onClick={() => setTier(t)}>{t === "guest" ? "访客" : t === "free" ? "免费" : "情报通"}</button>
        ))}
      </div>

      {user?.role === "admin" && (
        <button className="btn btn-ghost btn-sm" onClick={onAdmin}><IconUsers size={15} />后台</button>
      )}
      {user ? (
        <button className="btn btn-quiet btn-sm" onClick={onLogout}><IconLogout size={15} />退出</button>
      ) : (
        <button className="btn btn-ghost btn-sm" onClick={onLogin}><IconUser size={15} />登录</button>
      )}
    </div>
  );
}

// ───────────────────────── fixtures rail ─────────────────────────
const RAIL_FILTERS = ["全部", "今日", "英超", "欧冠", "意甲"];
function FixturesRail({ selectedId, onPick }) {
  const [filter, setFilter] = useState("全部");
  const list = useMemo(() => FIXTURES.filter(f =>
    filter === "全部" ? true : filter === "今日" ? f.date.includes("周六") || f.status === "live"
      : f.league.includes(filter)), [filter]);
  return (
    <div className="panel" style={{ height: "100%" }}>
      <div className="rail-head">
        <span className="sec-label"><span className="ic"><IconBall size={15} /></span>赛程</span>
        <button className="btn btn-quiet btn-sm" style={{ height: 28, padding: "0 8px" }}><IconRefresh size={14} /></button>
      </div>
      <div className="rail-filters">
        {RAIL_FILTERS.map(f => (
          <button key={f} className="chip" data-on={filter === f} onClick={() => setFilter(f)}
            style={{ padding: "5px 10px", fontSize: 12 }}>{f}</button>
        ))}
      </div>
      <div className="rail-list">
        {list.length === 0 && <div className="empty" style={{ padding: 24 }}><span style={{ fontSize: 13 }}>该筛选下暂无赛事</span></div>}
        {list.map(f => (
          <button key={f.id} className="fixture" data-active={f.id === selectedId} onClick={() => onPick(f.id)}>
            <div className="fixture-top">
              <span className="fixture-league">{f.league}</span>
              {f.status === "live" ? <span className="tag tag-warn" style={{ background: "#f6e4dd", color: "var(--danger-ink)" }}>LIVE</span> : null}
            </div>
            <div className="fixture-teams">{f.home}<span className="vs">VS</span>{f.away}</div>
            <div className="fixture-meta">
              <StatusDot status={f.status} />
              <span>{f.date} {f.kickoff}</span>
              <span style={{ marginLeft: "auto", color: "var(--ink-faint)" }}>数据{f.density}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ───────────────────────── match hero + ask ─────────────────────────
function MatchHero({ match }) {
  return (
    <div className="hero">
      <div className="hero-meta"><span>{match.league}</span><span className="sep">·</span><span>{match.date} {match.kickoff}</span></div>
      <div className="hero-teams">
        <span className="hero-team">{match.home}</span>
        <span className="hero-vs">VS</span>
        <span className="hero-team">{match.away}</span>
      </div>
      <div className="hero-foot">
        <span className="hero-pill"><IconEye size={13} style={{ verticalAlign: "-2px", marginRight: 5 }} />公开倾向 · {match.lean}</span>
        <div className="hero-stat"><b>{match.density}</b><span>情报密度</span></div>
        <div className="hero-stat"><b className="mono">{match.hours <= 0 ? "进行中" : `T-${match.hours}h`}</b><span>距开赛</span></div>
      </div>
    </div>
  );
}

function AskBox({ match, question, setQuestion, onAsk, running, tier }) {
  return (
    <div className="card ask">
      <span className="sec-label"><span className="ic"><IconSpark size={15} /></span>问这场比赛</span>
      <div className="ask-row">
        <input className="input grow" value={question} placeholder="例如：全场角球数预测是多少？"
          onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter") onAsk(); }} />
        <button className="btn btn-primary" disabled={running} onClick={() => onAsk()}>
          {running ? "研判中…" : <>开始研判 <IconArrowRight size={16} /></>}
        </button>
      </div>
      <div className="ask-chips">
        {QUESTION_PRESETS.map(p => (
          <button key={p.id} className="chip" onClick={() => onAsk(p.prompt)}>{p.label}</button>
        ))}
      </div>
      <div className="ask-hint"><IconShieldCheck size={14} />研判结论不构成投注建议；缺数据时如实说明，不编造倾向。</div>
    </div>
  );
}

function IdleHint({ tier }) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div className="empty">
        <span className="empty-ic"><IconSearch size={26} /></span>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>选一个问题，开始情报研判</div>
        <p style={{ fontSize: 13, maxWidth: "44ch", margin: 0 }}>
          我们会实时跑一遍「核验 → 采集 → 归一 → 打分 → 研判」的情报循环，逐条点亮信源，再给出带置信度的结论。
        </p>
      </div>
    </div>
  );
}

// ───────────────────────── report ─────────────────────────
function ReportView({ result, canDeep, tier, onUnlock, onAuth }) {
  const { prediction, confidence, factors, evidence, cycle, confirmed, assessments, alternatives, nextSteps, sources } = result;
  const okSources = sources.filter(s => s.status === "ok").length;

  return (
    <div className="report fade-up">
      <VerdictCard prediction={prediction} confidence={confidence} />

      <RSection icon={<IconLayers size={16} />} title="情报循环"
        right={<span className="tag tag-mute">{okSources}/{sources.length} 信源命中</span>}>
        <IntelCycle stages={cycle} />
      </RSection>

      {/* deep sections — gated */}
      <div className={canDeep ? "" : "locked"}>
        {!canDeep && (
          <div className="locked-veil">
            <div className="lk">
              <span className="empty-ic" style={{ margin: "0 auto 12px", background: "var(--gold-tint)", color: "var(--gold-deep)" }}><IconLock size={24} /></span>
              <div style={{ fontSize: 16, fontWeight: 700 }}>{tier === "guest" ? "注册即可查看完整证据链" : "升级「情报通」解锁全部"}</div>
              <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: "8px 0 14px" }}>
                证据链、因子权重与贝叶斯轨迹是研判的依据所在。
              </p>
              <button className="btn btn-gold" onClick={tier === "guest" ? onAuth : onUnlock}>
                <IconCrown size={16} />{tier === "guest" ? "用邀请码注册" : "解锁完整研判"}
              </button>
            </div>
          </div>
        )}

        <div className="report" style={{ filter: canDeep ? "none" : "blur(2px)", pointerEvents: canDeep ? "auto" : "none" }}>
          <RSection icon={<IconGraph size={16} />} title="因子权重"
            right={<span className="tag tag-mute">← 利主 / 利客 →</span>}>
            <FactorBars factors={factors} />
          </RSection>

          <RSection icon={<IconSearch size={16} />} title="证据链"
            right={<span className="tag tag-green">{evidence.length} 条</span>}>
            <EvidenceList items={evidence} />
          </RSection>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <RSection icon={<IconCheckCircle size={16} />} title="确认事实">
              <FindingList items={confirmed} />
            </RSection>
            <RSection icon={<IconScale size={16} />} title="研判推断">
              <FindingList items={assessments} />
            </RSection>
          </div>

          {alternatives.length > 0 && (
            <RSection icon={<IconAlert size={16} />} title="替代解释">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.8, color: "var(--ink-2)" }}>
                {alternatives.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </RSection>
          )}

          <RSection icon={<IconClock size={16} />} title="下一步 / 复扫计划"
            right={confidence.level && <ConfBadge level={confidence.level} />}>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.8, color: "var(--ink-2)" }}>
              {nextSteps.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
            <div style={{ marginTop: 12, fontSize: 12, color: "var(--ink-faint)" }}>
              置信度依据：{confidence.reason}
            </div>
          </RSection>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── right column ─────────────────────────
function AccountPanel({ user, tier, history, onLogin, onRegister, onUnlock, onAdmin }) {
  return (
    <div className="panel" style={{ height: "100%" }}>
      <div className="acct">
        {user ? (
          <div className="acct-card">
            <div className="acct-head">
              <span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>
              <div className="grow">
                <div style={{ fontWeight: 700, fontSize: 14 }}>{user.name}</div>
                <div style={{ marginTop: 3 }}><TierBadge tier={tier} /></div>
              </div>
            </div>
            <div className="hr" style={{ margin: "13px 0" }} />
            {tier === "paid" ? (
              <div className="quota">
                <span className="quota-ring" style={{ "--p": 100 }}><i>∞</i></span>
                <div><div style={{ fontWeight: 700, fontSize: 13 }}>无限研判</div>
                  <div style={{ fontSize: 11.5, color: "var(--ink-soft)" }}>会员有效期至 2026-07-17</div></div>
              </div>
            ) : (
              <div className="quota">
                <span className="quota-ring" style={{ "--p": (user.quota ?? 0) * 100 }}><i>{user.quota ?? 0}/1</i></span>
                <div className="grow"><div style={{ fontWeight: 700, fontSize: 13 }}>今日免费额度</div>
                  <div style={{ fontSize: 11.5, color: "var(--ink-soft)" }}>明日 00:00 重置</div></div>
              </div>
            )}
          </div>
        ) : (
          <div className="acct-card">
            <div style={{ fontWeight: 700, fontSize: 14 }}>访客模式</div>
            <p style={{ fontSize: 12.5, color: "var(--ink-soft)", margin: "8px 0 12px", lineHeight: 1.6 }}>
              注册后每天可免费完整研判 1 次，并查看证据链与置信度。
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary btn-sm grow" onClick={onRegister}><IconKey size={15} />邀请码注册</button>
              <button className="btn btn-ghost btn-sm" onClick={onLogin}>登录</button>
            </div>
          </div>
        )}

        {tier !== "paid" && (
          <div className="paywall">
            <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}><IconCrown size={18} style={{ color: "var(--gold-deep)" }} />情报通会员</h3>
            <ul className="paywall-feat">
              {UNLOCK_FEATURES.map(f => <li key={f}><IconCheck size={15} style={{ color: "var(--gold-deep)" }} />{f}</li>)}
            </ul>
            <button className="btn btn-gold btn-block" onClick={onUnlock} style={{ position: "relative" }}>
              ¥39/月 · 解锁完整研判
            </button>
          </div>
        )}

        <div>
          <span className="sec-label"><span className="ic"><IconDoc size={15} /></span>研判历史</span>
          <div style={{ marginTop: 8 }}>
            {history.length === 0 ? (
              <p style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>暂无记录，选一场比赛开始研判。</p>
            ) : history.map((h, i) => (
              <div className="hist-item" key={i}>
                <span className="hist-q">{h.q}</span>
                <span className="hist-meta"><ConfBadge level={h.level} withLabel={false} /> {h.match} · {h.at}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="grow" />
        <div style={{ fontSize: 11, color: "var(--ink-faint)", lineHeight: 1.7, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
          研判结论不构成投注建议 · 缺数据时明说，不编造倾向<br />
          <a href="#" style={{ color: "var(--gold-deep)" }}>用户协议</a> · <a href="#" style={{ color: "var(--gold-deep)" }}>隐私政策</a>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── paywall modal ─────────────────────────
function PaywallModal({ onClose, onPaid }) {
  const [tab, setTab] = useState("pay");
  const [code, setCode] = useState("");
  return (
    <div className="modal-veil" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-hd">
          <span className="sec-label"><span className="ic"><IconCrown size={16} /></span>解锁完整研判</span>
          <button className="x-btn" onClick={onClose}><IconX size={16} /></button>
        </div>
        <div className="modal-bd">
          <div className="pricing" style={{ marginTop: 0 }}>
            {PLANS.map(p => (
              <div className="plan" data-feature={p.feature} key={p.id}>
                {p.feature && <span className="plan-tag">最受欢迎</span>}
                <h3>{p.name}</h3>
                <div className="price"><span>¥</span><b>{p.price}</b><span>{p.unit}</span></div>
                <ul>{p.items.map(it => <li key={it}><IconCheck size={15} />{it}</li>)}</ul>
                <button className={`btn ${p.feature ? "btn-gold" : "btn-ghost"} btn-block`}
                  onClick={p.feature ? onPaid : (p.id === "free" ? () => setTab("code") : onClose)}>
                  {p.cta}
                </button>
              </div>
            ))}
          </div>

          <div className="hr" style={{ margin: "20px 0" }} />
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="field grow" style={{ minWidth: 200 }}>
              <label>有兑换码？</label>
              <input className="input" placeholder="输入兑换码，立即升级" value={code} onChange={e => setCode(e.target.value)} />
            </div>
            <button className="btn btn-primary" disabled={!code} onClick={onPaid}><IconKey size={15} />兑换</button>
          </div>
          <p style={{ fontSize: 11.5, color: "var(--ink-faint)", marginTop: 14, lineHeight: 1.7 }}>
            支付仅解锁分析能力，不构成任何投注建议。会员可随时取消，按自然月计费。
          </p>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── admin modal ─────────────────────────
function AdminModal({ onClose }) {
  const [tab, setTab] = useState("users");
  return (
    <div className="modal-veil" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 820 }}>
        <div className="modal-hd">
          <span className="sec-label"><span className="ic"><IconUsers size={16} /></span>运营后台</span>
          <button className="x-btn" onClick={onClose}><IconX size={16} /></button>
        </div>
        <div className="modal-bd">
          <div className="stat-grid">
            {ADMIN_STATS.map(s => (
              <div className="stat-box" key={s.k}><div className="v">{s.v}</div><div className="k">{s.k}</div></div>
            ))}
          </div>

          <div className="auth-tabs" style={{ maxWidth: 280 }}>
            <button className="auth-tab" data-on={tab === "users"} onClick={() => setTab("users")}>用户</button>
            <button className="auth-tab" data-on={tab === "invites"} onClick={() => setTab("invites")}>邀请码</button>
          </div>

          {tab === "users" ? (
            <table className="tbl">
              <thead><tr><th>用户名</th><th>等级</th><th>注册日</th><th>研判数</th><th>到期</th></tr></thead>
              <tbody>{ADMIN_USERS.map(u => (
                <tr key={u.name}>
                  <td style={{ fontWeight: 600 }}>{u.name}</td>
                  <td><TierBadge tier={u.tier} /></td>
                  <td className="mono" style={{ color: "var(--ink-soft)" }}>{u.joined}</td>
                  <td className="mono">{u.jobs}</td>
                  <td className="mono" style={{ color: "var(--ink-soft)" }}>{u.expires}</td>
                </tr>
              ))}</tbody>
            </table>
          ) : (
            <table className="tbl">
              <thead><tr><th>邀请码</th><th>使用</th><th>来源</th><th>状态</th></tr></thead>
              <tbody>{ADMIN_INVITES.map(c => (
                <tr key={c.code}>
                  <td className="mono" style={{ fontWeight: 600 }}>{c.code}</td>
                  <td className="mono">{c.used}/{c.cap}</td>
                  <td style={{ color: "var(--ink-soft)" }}>{c.by}</td>
                  <td>{c.st === "active" ? <span className="tag tag-green">可用</span> : <span className="tag tag-mute">已用尽</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm"><IconKey size={14} />生成新邀请码</button>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { App });
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
