// report-redesign.jsx — 3 alternative information architectures for the
// match analysis report, compared against the current (baseline) layout.
// Reuses existing tokens/icons/components/data from this project; adds only
// new, uniquely-prefixed ("rr-") CSS + components so nothing else is touched.
const { useState } = React;

const match = FIXTURES[0];
const result = buildAnalysis(match); // FIXTURES[0] has density "高" → resolves to the rich (non-insufficient) analysis
const { prediction, confidence, factors, evidence, cycle, confirmed, assessments, alternatives, nextSteps } = result;

// crude mock links from evidence → the finding/factor it backs, just for variant B
const SUPPORTS = {
  e1: { kind: "confirmed", id: "c1" },
  e2: { kind: "confirmed", id: "c2" },
  e3: { kind: "assessment", id: "a2" },
  e4: { kind: "assessment", id: "a1" },
  e5: { kind: "confirmed", id: "c1" },
};
const FINDING_BY_ID = {};
[...confirmed, ...assessments].forEach(f => { FINDING_BY_ID[f.id] = f; });

// ───────────────────────── shared bits ─────────────────────────
function MatchStrip() {
  return (
    <div className="rr-strip">
      <span className="rr-strip-league">{match.league}</span>
      <span className="rr-strip-teams">{match.home} <i>VS</i> {match.away}</span>
      <span className="rr-strip-meta">{match.date} {match.kickoff} · T-{match.hours}h</span>
    </div>
  );
}

function Accordion({ items, defaultOpen = [] }) {
  const [open, setOpen] = useState(() => new Set(defaultOpen));
  const toggle = (k) => setOpen(prev => {
    const next = new Set(prev);
    next.has(k) ? next.delete(k) : next.add(k);
    return next;
  });
  return (
    <div className="rr-acc">
      {items.map(it => {
        const isOpen = open.has(it.key);
        return (
          <div className="rr-acc-item" data-open={isOpen} key={it.key}>
            <button className="rr-acc-trigger" onClick={() => toggle(it.key)}>
              <span className="rr-acc-ic">{it.icon}</span>
              <span className="rr-acc-title">{it.title}</span>
              {it.badge}
              <span className="rr-acc-chev">{isOpen ? "−" : "+"}</span>
            </button>
            {isOpen && <div className="rr-acc-body">{it.content}</div>}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════ Variant A ═══════════════════════════
// 结论优先 · 分层卡片 — 3 visual tiers: verdict (always) → confirmed vs
// inferred (always, the actionable middle) → everything else (accordion).
function ReportTieredA() {
  return (
    <div className="rr-stack">
      <VerdictCard prediction={prediction} confidence={confidence} />

      <div className="rr-tier2">
        <div className="rr-tier2-col">
          <div className="rr-tier2-hd"><IconCheckCircle size={15} />确认事实</div>
          <FindingList items={confirmed} />
        </div>
        <div className="rr-tier2-col">
          <div className="rr-tier2-hd"><IconScale size={15} />研判推断</div>
          <FindingList items={assessments} />
        </div>
      </div>

      {alternatives.length > 0 && (
        <div className="rr-altnote">
          <IconAlert size={15} />
          <div>
            <b>替代解释</b>
            <ul>{alternatives.map((a, i) => <li key={i}>{a}</li>)}</ul>
          </div>
        </div>
      )}

      <Accordion
        defaultOpen={["factors"]}
        items={[
          {
            key: "cycle", icon: <IconLayers size={15} />, title: "情报循环",
            badge: <span className="tag tag-mute" style={{ marginLeft: "auto" }}>4/4 阶段</span>,
            content: <IntelCycle stages={cycle} />,
          },
          {
            key: "factors", icon: <IconGauge size={15} />, title: "因子权重",
            badge: <span className="tag tag-mute" style={{ marginLeft: "auto" }}>← 利主 / 利客 →</span>,
            content: <FactorBars factors={factors} />,
          },
          {
            key: "evidence", icon: <IconSearch size={15} />, title: "证据链",
            badge: <span className="tag tag-green" style={{ marginLeft: "auto" }}>{evidence.length} 条</span>,
            content: <EvidenceList items={evidence} />,
          },
          {
            key: "next", icon: <IconClock size={15} />, title: "下一步 / 复扫计划",
            badge: <ConfBadge level={confidence.level} />,
            content: (
              <>
                <ul className="rr-bullets">{nextSteps.map((s, i) => <li key={i}>{s}</li>)}</ul>
                <p className="rr-reason"><IconCircleDot size={12} />置信度依据：{confidence.reason}</p>
              </>
            ),
          },
        ]}
      />
    </div>
  );
}

// ═══════════════════════════ Variant B ═══════════════════════════
// 证据驱动 · 左右分栏 — left = sticky verdict + condensed factors (the
// "why"), right = evidence feed as the primary scroll, each item tagged
// with which finding it supports (the "proof").
function ReportSplitB() {
  return (
    <div className="rr-split">
      <div className="rr-split-left">
        <div className="rr-split-card">
          <div className="rr-tier2-hd" style={{ marginBottom: 10 }}><IconGauge size={15} />方向研判</div>
          <div className="rr-split-lean">{prediction.headline}</div>
          <ConfBadge level={confidence.level} />
          <ProbabilityBands bands={prediction.bands} lead={prediction.lead} />
        </div>

        <div className="rr-split-card">
          <div className="rr-tier2-hd" style={{ marginBottom: 10 }}><IconGraph size={15} />因子权重（精简）</div>
          <div className="rr-mini-factors">
            {factors.filter(f => f.enabled).slice(0, 4).map(f => (
              <div className="rr-mini-factor" key={f.id}>
                <span>{f.label}</span>
                <span className="rr-mini-factor-track">
                  <i data-dir={f.dir} style={{ width: `${Math.max(Math.round(Math.abs(f.impact) * 100), 8)}%` }} />
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rr-split-card">
          <div className="rr-tier2-hd" style={{ marginBottom: 8 }}><IconClock size={15} />下一步</div>
          <ul className="rr-bullets">{nextSteps.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </div>
      </div>

      <div className="rr-split-right">
        <div className="rr-split-right-hd">
          <IconSearch size={15} />
          <span>证据链 · 按到达时间</span>
          <span className="tag tag-green" style={{ marginLeft: "auto" }}>{evidence.length} 条</span>
        </div>
        {evidence.map(e => {
          const sup = SUPPORTS[e.id];
          const supFinding = sup ? FINDING_BY_ID[sup.id] : null;
          return (
            <div className="ev rr-split-ev" key={e.id}>
              <div className="ev-top">
                <span className="ev-src">{e.src}</span>
                {SIDE_TAG_MAP[e.side]}
                <span className="ev-time mono">{e.time}</span>
              </div>
              <p className="ev-claim">{e.claim}</p>
              <div className="ev-meter">
                <span className="lab">可信度</span>
                <span className="meter"><i style={{ width: `${e.conf * 100}%` }} /></span>
                <span className="lab" style={{ marginLeft: 8 }}>时效</span>
                <span className="meter"><i style={{ width: `${e.fresh * 100}%`, background: "var(--gold-deep)" }} /></span>
              </div>
              {supFinding && (
                <div className="rr-supports">
                  <IconArrowUpRight size={12} />
                  支持{sup.kind === "confirmed" ? "确认事实" : "研判推断"}：{supFinding.text}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
const SIDE_TAG_MAP = {
  home: <span className="tag tag-green">利主</span>,
  away: <span className="tag tag-gold">利客</span>,
  neutral: <span className="tag tag-mute">中性</span>,
  both: <span className="tag tag-info">双向</span>,
};

// ═══════════════════════════ Variant C ═══════════════════════════
// 标签页 · 聚焦单视图 — verdict always visible, everything else lives
// behind a segmented control so only one section occupies the screen.
const TABS_C = [
  { key: "cycle", label: "情报循环", icon: <IconLayers size={14} /> },
  { key: "factors", label: "因子权重", icon: <IconGauge size={14} /> },
  { key: "evidence", label: "证据链", icon: <IconSearch size={14} /> },
  { key: "findings", label: "确认 / 推断", icon: <IconCheckCircle size={14} /> },
  { key: "next", label: "替代 / 下一步", icon: <IconClock size={14} /> },
];
function ReportTabbedC() {
  const [tab, setTab] = useState("factors");
  return (
    <div className="rr-stack">
      <VerdictCard prediction={prediction} confidence={confidence} />

      <div className="rr-tabbar">
        {TABS_C.map(t => (
          <button key={t.key} className="rr-tab" data-on={tab === t.key} onClick={() => setTab(t.key)}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      <div className="rsec rr-tabpanel">
        {tab === "cycle" && <IntelCycle stages={cycle} />}
        {tab === "factors" && <FactorBars factors={factors} />}
        {tab === "evidence" && <EvidenceList items={evidence} />}
        {tab === "findings" && (
          <div className="rr-tier2" style={{ gap: 20 }}>
            <div className="rr-tier2-col">
              <div className="rr-tier2-hd"><IconCheckCircle size={15} />确认事实</div>
              <FindingList items={confirmed} />
            </div>
            <div className="rr-tier2-col">
              <div className="rr-tier2-hd"><IconScale size={15} />研判推断</div>
              <FindingList items={assessments} />
            </div>
          </div>
        )}
        {tab === "next" && (
          <>
            {alternatives.length > 0 && (
              <>
                <div className="rr-tier2-hd"><IconAlert size={15} />替代解释</div>
                <ul className="rr-bullets" style={{ marginBottom: 16 }}>{alternatives.map((a, i) => <li key={i}>{a}</li>)}</ul>
              </>
            )}
            <div className="rr-tier2-hd"><IconClock size={15} />下一步 / 复扫计划</div>
            <ul className="rr-bullets">{nextSteps.map((s, i) => <li key={i}>{s}</li>)}</ul>
            <p className="rr-reason"><IconCircleDot size={12} />置信度依据：{confidence.reason}</p>
          </>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════ Baseline (current shape) ═══════════════════════════
function ReportBaseline() {
  return (
    <div className="report">
      <VerdictCard prediction={prediction} confidence={confidence} />
      <RSection icon={<IconLayers size={16} />} title="情报循环" right={<span className="tag tag-mute">4/4 阶段</span>}>
        <IntelCycle stages={cycle} />
      </RSection>
      <RSection icon={<IconGauge size={16} />} title="因子权重" right={<span className="tag tag-mute">← 利主 / 利客 →</span>}>
        <FactorBars factors={factors} />
      </RSection>
      <RSection icon={<IconSearch size={16} />} title="证据链" right={<span className="tag tag-green">{evidence.length} 条</span>}>
        <EvidenceList items={evidence} />
      </RSection>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <RSection icon={<IconCheckCircle size={16} />} title="确认事实"><FindingList items={confirmed} /></RSection>
        <RSection icon={<IconScale size={16} />} title="研判推断"><FindingList items={assessments} /></RSection>
      </div>
      <RSection icon={<IconAlert size={16} />} title="替代解释">
        <ul className="rr-bullets">{alternatives.map((a, i) => <li key={i}>{a}</li>)}</ul>
      </RSection>
      <RSection icon={<IconClock size={16} />} title="下一步 / 复扫计划" right={<ConfBadge level={confidence.level} />}>
        <ul className="rr-bullets">{nextSteps.map((s, i) => <li key={i}>{s}</li>)}</ul>
        <p className="rr-reason"><IconCircleDot size={12} />置信度依据：{confidence.reason}</p>
      </RSection>
    </div>
  );
}

// ═══════════════════════════ page shell + switcher ═══════════════════════════
const VARIANTS = [
  { key: "baseline", label: "现状（基线）", desc: "全部区块纵向堆叠，逐个滚动查看", Comp: ReportBaseline },
  { key: "A", label: "方案 A · 分层卡片", desc: "结论优先：确认/推断常驻，其余收进可展开手风琴", Comp: ReportTieredA },
  { key: "B", label: "方案 B · 证据分栏", desc: "左：结论与精简因子常驻；右：证据链为主滚动区，标注证据支持哪条结论", Comp: ReportSplitB },
  { key: "C", label: "方案 C · 标签聚焦", desc: "结论常驻，其余区块做成标签页，每次只看一个板块", Comp: ReportTabbedC },
];

function Page() {
  const [active, setActive] = useState("A");
  const variant = VARIANTS.find(v => v.key === active);
  return (
    <div className="rr-page">
      <div className="rr-switcher">
        <div className="rr-switcher-head">
          <span className="brand-mark" style={{ width: 30, height: 30, fontSize: 14, borderRadius: 9 }}>世</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14 }}>研判报告 · 展示区方案对比</div>
            <div style={{ fontSize: 11.5, color: "var(--ink-soft)" }}>{variant.desc}</div>
          </div>
        </div>
        <div className="rr-switcher-tabs">
          {VARIANTS.map(v => (
            <button key={v.key} className="rr-switch-btn" data-on={active === v.key} onClick={() => setActive(v.key)}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rr-canvas">
        <MatchStrip />
        <variant.Comp />
      </div>
    </div>
  );
}

Object.assign(window, { ReportBaseline, ReportTieredA, ReportSplitB, ReportTabbedC, Page });
ReactDOM.createRoot(document.getElementById("root")).render(<Page />);
