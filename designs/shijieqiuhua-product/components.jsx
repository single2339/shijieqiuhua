// components.jsx — presentational pieces (props in, no app state).
const { useState } = React;

const CONF_LABEL = { L1: "确认", L2: "高可信", L3: "中可信", L4: "推测" };
const ConfBadge = ({ level, withLabel = true }) => (
  <span className={`conf conf-${level}`}>{level}{withLabel ? ` · ${CONF_LABEL[level] || ""}` : ""}</span>
);

const TIER_LABEL = { guest: "访客", free: "免费会员", paid: "情报通" };
const TierBadge = ({ tier }) => (
  <span className={`tier-badge tier-${tier}`}>{TIER_LABEL[tier] || tier}</span>
);

const StatusDot = ({ status }) => {
  const cls = status === "live" ? "dot-live" : status === "soon" ? "dot-soon" : "dot-done";
  return <span className={`dot ${cls}`} />;
};

const SrcStatus = ({ status }) => {
  if (status === "ok") return <span className="src-status src-ok"><IconCheck size={13} />命中</span>;
  if (status === "skipped") return <span className="src-status src-skip"><IconCircleDot size={12} />跳过</span>;
  return <span className="src-status src-fail"><IconX size={12} />失败</span>;
};

// ── live phase tracker (collect → … → report) ──
function PhaseTracker({ phaseIdx, progress, feed }) {
  return (
    <div className="tracker fade-in">
      <div className="tracker-head">
        <span className="sec-label"><span className="ic"><IconSpark size={15} /></span>情报研判进行中</span>
        <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--brand)" }}>{progress}%</span>
      </div>

      <div className="phase-rail">
        {PHASES.map((p, i) => {
          const state = i < phaseIdx ? "done" : i === phaseIdx ? "active" : "todo";
          return (
            <div className="phase" data-state={state} key={p.key}>
              <div className="phase-node">
                <span className="phase-bead">
                  {state === "done" ? <IconCheck size={14} />
                    : state === "active" ? <span className="spin" />
                    : <span className="mono" style={{ fontSize: 11 }}>{i + 1}</span>}
                </span>
                <span className="phase-name">{p.name}</span>
                <span className="phase-line"><i /></span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress"><i style={{ width: `${progress}%` }} /></div>

      <div className="feed">
        {feed.map((f, i) => (
          <div className="feed-item" key={f.label + i} style={{ animationDelay: `${i * 40}ms` }}>
            <IconSearch size={14} style={{ color: "var(--ink-soft)" }} />
            <span className="src">{f.label}</span>
            <span className="why">· {f.why}</span>
            <SrcStatus status={f.status || "ok"} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── probability bands ──
const PB_META = {
  home_win: { label: "主胜", color: "var(--brand-600)" },
  draw: { label: "平局", color: "var(--gold-deep)" },
  away_win: { label: "客胜", color: "var(--ink-soft)" },
};
function ProbabilityBands({ bands, lead }) {
  return (
    <div className="prob">
      {["home_win", "draw", "away_win"].map((k) => {
        const [lo, hi] = bands[k];
        const mid = Math.round((lo + hi) / 2);
        return (
          <div className="prob-cell" data-lead={lead === k} key={k}>
            <h4>{PB_META[k].label}</h4>
            <div className="prob-val">{lo}–{hi}<small>%</small></div>
            <div className="prob-bar"><i style={{ width: `${mid}%`, background: PB_META[k].color }} /></div>
          </div>
        );
      })}
    </div>
  );
}

// ── factor impact bars (centered diverging) ──
const DIR_LABEL = { home: "利主", away: "利客", draw: "利平", neutral: "中性" };
function FactorBars({ factors }) {
  return (
    <div className="factors">
      {factors.map((f) => {
        const pct = Math.round(Math.abs(f.impact) * 50); // half-width max
        return (
          <div className="factor" data-disabled={!f.enabled} key={f.id}>
            <div className="factor-name">
              {f.label}
              <span className="gp">{f.group}</span>
            </div>
            <div className="factor-track">
              <span className="mid" />
              {f.enabled
                ? <span className="factor-fill" data-dir={f.dir} style={{ width: `${Math.max(pct, 3)}%` }} />
                : null}
            </div>
            <span className="factor-impact">
              {f.enabled ? `${f.dir === "neutral" ? "±" : f.dir === "home" ? "←" : "→"}${Math.abs(f.impact).toFixed(2)}` : "缺数据"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── evidence list ──
const SIDE_TAG = {
  home: <span className="tag tag-green">利主</span>,
  away: <span className="tag tag-gold">利客</span>,
  neutral: <span className="tag tag-mute">中性</span>,
  both: <span className="tag tag-info">双向</span>,
};
function EvidenceList({ items }) {
  return (
    <div className="evlist">
      {items.map((e) => (
        <div className="ev" key={e.id}>
          <div className="ev-top">
            <span className="ev-src">{e.src}</span>
            {SIDE_TAG[e.side]}
            <span className="ev-time mono">{e.time}</span>
          </div>
          <p className="ev-claim">{e.claim}</p>
          <div className="ev-meter">
            <span className="lab">可信度</span>
            <span className="meter"><i style={{ width: `${e.conf * 100}%` }} /></span>
            <span className="lab" style={{ marginLeft: 8 }}>时效</span>
            <span className="meter"><i style={{ width: `${e.fresh * 100}%`, background: "var(--gold-deep)" }} /></span>
            <a className="ev-time mono" href={`https://${e.url}`} target="_blank" rel="noreferrer"
              style={{ marginLeft: "auto", color: "var(--ink-faint)", textDecoration: "none" }}>{e.url} ↗</a>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── intelligence cycle ──
const CY_TAG = { completed: "tag-green", partial: "tag-warn", skipped: "tag-mute" };
const CY_LABEL = { completed: "完成", partial: "部分", skipped: "跳过" };
function IntelCycle({ stages }) {
  return (
    <div className="cycle">
      {stages.map((s, i) => (
        <div className="cycle-step" data-st={s.st} key={s.name}>
          <h4><span className="mono" style={{ color: "var(--ink-faint)" }}>{i + 1}</span>{s.name}
            <span className={`tag ${CY_TAG[s.st]}`} style={{ marginLeft: "auto" }}>{CY_LABEL[s.st]}</span>
          </h4>
          <p>{s.desc}</p>
        </div>
      ))}
    </div>
  );
}

// ── findings (confirmed / assessment) ──
function FindingList({ items }) {
  if (!items.length) return <p style={{ fontSize: 13, color: "var(--ink-faint)" }}>本场暂无该类条目。</p>;
  return (
    <div>
      {items.map((f) => (
        <div className="finding" key={f.id}>
          <span className="finding-ic" data-t={f.t}>
            {f.t === "confirmed" ? <IconCheck size={14} /> : <IconScale size={13} />}
          </span>
          <div className="grow">
            <div className="finding-body">{f.text}</div>
            <div className="finding-body src" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <ConfBadge level={f.level} withLabel={false} /> {f.src}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── report section wrapper ──
function RSection({ icon, title, right, children }) {
  return (
    <div className="rsec">
      <div className="rsec-hd">
        <span style={{ color: "var(--brand-600)" }}>{icon}</span>
        <h3>{title}</h3>
        {right ? <span className="right">{right}</span> : null}
      </div>
      <div className="rsec-bd">{children}</div>
    </div>
  );
}

// ── verdict header card ──
function VerdictCard({ prediction, confidence }) {
  const insufficient = prediction.lean === "info_insufficient";
  return (
    <div className="verdict" data-insufficient={insufficient}>
      <div className="verdict-top">
        <div>
          <span className="sec-label"><span className="ic"><IconGauge size={15} /></span>方向研判</span>
          <div className="verdict-lean" style={{ marginTop: 8 }}>{prediction.headline}</div>
        </div>
        <ConfBadge level={confidence.level} />
      </div>
      <p className="verdict-sum">{prediction.summary}</p>
      {insufficient && (
        <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 9, fontSize: 12.5,
          color: "var(--danger-ink)", fontWeight: 600 }}>
          <IconShieldCheck size={16} />我们没编。缺关键数据时如实说明，开赛前会自动复扫。
        </div>
      )}
      {!insufficient && prediction.bands && (
        <ProbabilityBands bands={prediction.bands} lead={prediction.lead} />
      )}
      {prediction.scoreline.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>比分倾向</span>
          {prediction.scoreline.map((s) => (
            <span className="chip mono" key={s} style={{ fontWeight: 700 }}>{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── toast ──
function Toast({ msg }) {
  if (!msg) return null;
  return (
    <div className="toast-wrap">
      <div className="toast"><IconCheckCircle size={16} />{msg}</div>
    </div>
  );
}

Object.assign(window, {
  ConfBadge, TierBadge, StatusDot, SrcStatus, PhaseTracker, ProbabilityBands,
  FactorBars, EvidenceList, IntelCycle, FindingList, RSection, VerdictCard, Toast,
});
