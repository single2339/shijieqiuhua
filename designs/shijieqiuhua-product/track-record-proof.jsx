// track-record-proof.jsx — the "public track record" proof section for the
// landing page. Presentational only: takes a data object, renders big-number
// stats, a rolling-accuracy sparkline (real SVG path from the trend array,
// not decorative art), and a card grid of recent settled matches.

function buildSparkline(values, w, h, pad) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = (max - min) || 1;
  const stepX = (w - pad * 2) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = pad + i * stepX;
    const y = pad + (1 - (v - min) / range) * (h - pad * 2);
    return [x, y];
  });
  const line = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${h - pad} L${pts[0][0].toFixed(1)},${h - pad} Z`;
  return { line, area, last: pts[pts.length - 1] };
}

function TrendChart({ trend }) {
  const w = 320, h = 88, pad = 8;
  const { line, area, last } = buildSparkline(trend, w, h, pad);
  const latest = trend[trend.length - 1];
  return (
    <div className="proof-chart-card">
      <div className="proof-chart-label">
        <span>近 {trend.length} 期方向命中率走势</span>
        <b className="mono proof-chart-latest">{latest}%</b>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="proof-chart-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id="proofTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--gold)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="var(--gold)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#proofTrendFill)" stroke="none" />
        <path d={line} fill="none" stroke="var(--gold)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={last[0]} cy={last[1]} r="4" fill="var(--gold-deep)" stroke="var(--brand-700)" strokeWidth="2" />
      </svg>
    </div>
  );
}

function MatchCard({ r }) {
  return (
    <div className="proof-card" data-hit={r.hit}>
      <div className="proof-card-top">
        <span className="tag tag-mute">{r.league}</span>
        <span className="proof-card-date mono">{r.date}</span>
      </div>
      <div className="proof-card-teams">{r.home}<span className="vs">vs</span>{r.away}</div>
      <div className="proof-card-row"><span className="lab">研判</span><span>{r.lean} · {r.band}</span></div>
      <div className="proof-card-row"><span className="lab">实际比分</span><span className="mono proof-card-score">{r.actualHome}-{r.actualAway}</span></div>
      <div className="proof-card-badge" data-hit={r.hit}>
        {r.hit ? <IconCheck size={13} /> : <IconX size={13} />}
        {r.hit ? "命中" : "未中"}
      </div>
    </div>
  );
}

function TrackRecordProof({ data }) {
  const { settled, leanAccuracy, scorelineAccuracy, trend, recent } = data;
  return (
    <section className="proof" id="record">
      <div className="proof-inner land-wrap">
        <div className="proof-head">
          <div className="proof-kicker"><IconShieldCheck size={14} />公开战绩 · 非营销话术</div>
          <h2 className="proof-title">每一条判断，事后都对得上账</h2>
          <p className="proof-sub">
            我们记录每一场给出明确方向的研判，比赛结束后用第三方数据源核对实际结果。
            模糊倾向（如「主胜或平」）与「信息不足」不计入命中率统计——拒绝靠宽松口径粉饰战绩。
          </p>
        </div>

        <div className="proof-stats">
          <div className="proof-stat">
            <b className="mono">{settled}</b>
            <span>场已结算判断</span>
          </div>
          <div className="proof-stat proof-stat--accent">
            <b className="mono">{Math.round(leanAccuracy * 100)}%</b>
            <span>方向命中率</span>
          </div>
          <div className="proof-stat">
            <b className="mono">{Math.round(scorelineAccuracy * 100)}%</b>
            <span>比分区间命中率</span>
          </div>
        </div>

        <div className="proof-chart-row">
          <TrendChart trend={trend} />
          <div className="proof-rule">
            <IconScale size={18} />
            <p>只统计 <b>主胜 / 主负 / 平局</b> 这类明确方向的判断；遇到「主胜或平」式模糊倾向、或证据不足时我们直接说「信息不足」——这部分不参与命中率计算，也不会拉低或美化数字。</p>
          </div>
        </div>

        <div className="proof-cards-head">
          <h3>最近战绩</h3>
          <a className="proof-more" href="#how">查看研判方法论 <IconArrowRight size={14} /></a>
        </div>
        <div className="proof-cards">
          {recent.map((r) => <MatchCard key={`${r.home}-${r.away}-${r.date}`} r={r} />)}
        </div>
      </div>
    </section>
  );
}

Object.assign(window, { TrackRecordProof });
