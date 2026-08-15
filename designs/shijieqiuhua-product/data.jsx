// data.jsx — mock fixtures + OSINT analysis payloads + product data.
// Mirrors backend/football_osint shapes (sources, evidence, factors,
// prediction bands, confidence L1–L4, intelligence cycle, findings).

const QUESTION_PRESETS = [
  { id: "goals", label: "全场比分", prompt: "全场比分预测是多少？" },
  { id: "corners", label: "角球数", prompt: "全场角球数预测是多少？" },
  { id: "cards", label: "红黄牌", prompt: "全场红黄牌的预测数量是多少？" },
  { id: "half", label: "半场", prompt: "上半场比分预计是多少？" },
  { id: "player", label: "核心球员", prompt: "核心球员状态会怎样影响比赛？" },
  { id: "risk", label: "临场风险", prompt: "这场比赛最大的临场风险是什么？" },
];

const FIXTURES = [
  { id: "epl-ars-mci", league: "英超 · 第32轮", kickoff: "今晚 20:30", date: "周六", status: "soon",
    home: "阿森纳", away: "曼城", lean: "主队微弱占优", density: "高", hours: 4.5 },
  { id: "ucl-rma-bay", league: "欧冠 · 半决赛", kickoff: "明晨 03:00", date: "周三", status: "scheduled",
    home: "皇家马德里", away: "拜仁慕尼黑", lean: "数据分歧大", density: "高", hours: 28 },
  { id: "sea-int-juv", league: "意甲 · 第31轮", kickoff: "今晚 02:45", date: "周日", status: "live",
    home: "国际米兰", away: "尤文图斯", lean: "进行中 1-0", density: "中", hours: 0 },
  { id: "lal-bar-atm", league: "西甲 · 第30轮", kickoff: "明晚 23:00", date: "周日", status: "scheduled",
    home: "巴塞罗那", away: "马德里竞技", lean: "平局压力偏高", density: "中", hours: 25 },
  { id: "bun-bvb-rbl", league: "德甲 · 第29轮", kickoff: "后天 21:30", date: "周一", status: "scheduled",
    home: "多特蒙德", away: "莱比锡", lean: "数据稀薄", density: "低", hours: 50 },
  { id: "l1-psg-mar", league: "法甲 · 第30轮", kickoff: "后天 03:45", date: "周二", status: "scheduled",
    home: "巴黎圣日耳曼", away: "马赛", lean: "主队方向占优", density: "高", hours: 52 },
];

// ── phase plan for the live tracker ──
const PHASES = [
  { key: "verify",    name: "核验", desc: "确认比赛主体、时间、场地" },
  { key: "collect",   name: "采集", desc: "多源情报抓取与去重" },
  { key: "normalize", name: "归一", desc: "翻译、结构化、时效评分" },
  { key: "score",     name: "打分", desc: "因子加权、贝叶斯更新" },
  { key: "report",    name: "研判", desc: "生成结论与置信度" },
];

// Source pool that "lights up" during collection.
const SOURCE_POOL = [
  { adapter: "official", label: "俱乐部官网公告", why: "首发与伤停官方口径" },
  { adapter: "press", label: "Goal / BBC Sport", why: "赛前发布会要点" },
  { adapter: "press2", label: "The Athletic", why: "战术与轮换分析" },
  { adapter: "stat", label: "FBref / Opta", why: "近6场 xG、角球趋势" },
  { adapter: "social", label: "记者 X 动态", why: "训练场最新画面" },
  { adapter: "weather", label: "气象台", why: "开赛时段天气" },
  { adapter: "market", label: "公开盘口异动", why: "情绪面参照（不作结论）" },
];

const fmtTime = (h) => {
  const d = new Date(Date.now() - h * 3600_000);
  return d.toISOString().slice(11, 16);
};

// Rich analysis for a well-covered match.
function richAnalysis(match, question) {
  return {
    kind: "sufficient",
    sources: [
      { adapter: "official", label: "阿森纳官网公告", status: "ok", reason: "首发名单已发布", n: 2 },
      { adapter: "press", label: "BBC Sport", status: "ok", reason: "赛前发布会纪要", n: 3 },
      { adapter: "press2", label: "The Athletic", status: "ok", reason: "轮换与战术拆解", n: 2 },
      { adapter: "stat", label: "FBref / Opta", status: "ok", reason: "近6场结构化数据", n: 4 },
      { adapter: "social", label: "记者 X 动态", status: "ok", reason: "训练画面交叉印证", n: 2 },
      { adapter: "weather", label: "气象台", status: "ok", reason: "晴, 微风 2级", n: 1 },
      { adapter: "market", label: "公开盘口异动", status: "skipped", reason: "仅作情绪参照，不纳入结论", n: 0 },
    ],
    prediction: {
      lean: "home_or_draw",
      headline: "主队不败方向，进球数偏高",
      summary:
        "阿森纳主场近况稳健、核心中场齐整，曼城客场轮换迹象明显且中卫一人停赛。综合首发、近期 xG 与对位历史，主队不败是当前证据支持度最高的方向；双方进攻效率都不低，全场进球数倾向于 2.5 球以上。",
      bands: {
        home_win: [44, 52], draw: [24, 30], away_win: [22, 28],
      },
      lead: "home_win",
      scoreline: ["2-1", "1-1", "2-0"],
      drivers: ["主队首发完整", "客队中卫停赛", "近6场角球趋势"],
      uncertainties: ["客队门将伤情待确认", "裁判尺度偏严可能抬高牌数"],
    },
    confidence: { level: "L2", label: "高可信", reason: "关键事实有 2 个以上独立信源印证，仅 1 项次要信息待确认。" },
    factors: [
      { id: "lineup_home", label: "主队首发完整度", group: "阵容", dir: "home", impact: 0.72, weight: 0.9, enabled: true, n: 3 },
      { id: "suspension_away", label: "客队中卫停赛", group: "阵容", dir: "home", impact: 0.55, weight: 0.8, enabled: true, n: 2 },
      { id: "form_home", label: "主场近况 (xG)", group: "状态", dir: "home", impact: 0.41, weight: 0.7, enabled: true, n: 4 },
      { id: "rotation_away", label: "客队轮换迹象", group: "状态", dir: "home", impact: 0.33, weight: 0.6, enabled: true, n: 2 },
      { id: "h2h", label: "对位历史", group: "历史", dir: "neutral", impact: 0.08, weight: 0.4, enabled: true, n: 2 },
      { id: "keeper_away", label: "客队门将伤情", group: "阵容", dir: "away", impact: 0.0, weight: 0.5, enabled: false, n: 0, missing: "信息未确认，暂不计入" },
      { id: "weather", label: "天气影响", group: "环境", dir: "neutral", impact: 0.03, weight: 0.2, enabled: true, n: 1 },
    ],
    evidence: [
      { id: "e1", src: "阿森纳官网", url: "arsenal.com/teams", time: fmtTime(3.2), side: "home",
        claim: "官方首发公布：厄德高、赖斯、萨卡均进入首发，无新增伤停。", conf: 0.95, fresh: 0.98 },
      { id: "e2", src: "BBC Sport", url: "bbc.com/sport", time: fmtTime(5.0), side: "away",
        claim: "曼城官方确认中卫因累计黄牌停赛一场，瓜迪奥拉暗示部分主力轮休。", conf: 0.88, fresh: 0.9 },
      { id: "e3", src: "FBref", url: "fbref.com", time: fmtTime(8), side: "neutral",
        claim: "近6场两队场均合计 xG 3.1，主队主场角球场均 6.8。", conf: 0.9, fresh: 0.7 },
      { id: "e4", src: "The Athletic", url: "theathletic.com", time: fmtTime(6.5), side: "home",
        claim: "记者分析：曼城客场三线作战，本场更可能保守换人，让出中场控制。", conf: 0.7, fresh: 0.85 },
      { id: "e5", src: "记者 X", url: "x.com", time: fmtTime(2.1), side: "neutral",
        claim: "训练场画面显示主队核心球员均参与合练，状态正常。", conf: 0.62, fresh: 0.95 },
    ],
    cycle: [
      { name: "收集", st: "completed", desc: "6 个信源命中，1 个按规则跳过，去重后 14 条原始情报。" },
      { name: "加工", st: "completed", desc: "全部翻译并结构化，按时效与来源可信度打分。" },
      { name: "开发", st: "completed", desc: "因子加权 + 贝叶斯更新，交叉验证关键事实。" },
      { name: "生产", st: "completed", desc: "形成方向研判、概率区间与置信度评级。" },
    ],
    confirmed: [
      { id: "c1", text: "主队本场首发完整，无新增伤停。", t: "confirmed", level: "L1", src: "官网 + 记者画面 双源" },
      { id: "c2", text: "客队 1 名主力中卫停赛。", t: "confirmed", level: "L1", src: "官网 + BBC 双源" },
    ],
    assessments: [
      { id: "a1", text: "客队倾向于客场轮换、让出中场控制权。", t: "assessment", level: "L3", src: "单一记者分析，属推断" },
      { id: "a2", text: "全场进球数偏向 2.5 以上。", t: "assessment", level: "L2", src: "基于双方近期 xG 结构" },
    ],
    alternatives: [
      "若客队门将确认伤缺并由替补出战，客队失球概率上升，主胜方向进一步增强。",
      "若裁判尺度偏严，牌数与点球风险上升，比赛走向可能更碎片化。",
    ],
    nextSteps: [
      "开赛前 2 小时复扫官方首发，确认门将伤情。",
      "关注客队是否官宣轮休名单。",
    ],
  };
}

// Honest "not enough data" result — the product's differentiator.
function insufficientAnalysis(match) {
  return {
    kind: "insufficient",
    sources: [
      { adapter: "official", label: "俱乐部官网", status: "ok", reason: "仅赛程，无首发", n: 1 },
      { adapter: "press", label: "本地媒体", status: "ok", reason: "无赛前发布会", n: 1 },
      { adapter: "stat", label: "FBref / Opta", status: "ok", reason: "样本偏少", n: 2 },
      { adapter: "social", label: "记者 X 动态", status: "failed", reason: "无可信训练情报", n: 0 },
      { adapter: "official2", label: "客队官网", status: "skipped", reason: "距开赛 50 小时，信息未释放", n: 0 },
    ],
    prediction: {
      lean: "info_insufficient",
      headline: "信息不足，暂不给方向",
      summary:
        "距开赛超过 48 小时，双方均未释放首发与伤停的官方口径，可用情报仅为历史数据。在缺少关键阵容信息的情况下，给出方向性结论会显著降低可靠性——我们选择如实说明，而不是编一个倾向。",
      bands: null,
      scoreline: [],
      drivers: [],
      uncertainties: ["首发未知", "伤停未知", "轮换计划未知"],
    },
    confidence: { level: "L4", label: "推测/不足", reason: "关键阵容信息缺失，现有证据不足以支撑方向研判。" },
    factors: [
      { id: "history", label: "对位历史", group: "历史", dir: "neutral", impact: 0.12, weight: 0.4, enabled: true, n: 2 },
      { id: "lineup", label: "双方首发", group: "阵容", dir: "neutral", impact: 0, weight: 0.95, enabled: false, n: 0, missing: "官方尚未发布" },
      { id: "injury", label: "伤停情况", group: "阵容", dir: "neutral", impact: 0, weight: 0.85, enabled: false, n: 0, missing: "无可信来源" },
      { id: "form", label: "近期状态", group: "状态", dir: "neutral", impact: 0.18, weight: 0.6, enabled: true, n: 2 },
    ],
    evidence: [
      { id: "e1", src: "FBref", url: "fbref.com", time: fmtTime(20), side: "neutral",
        claim: "两队历史交锋近5场 2胜1平2负，无明显方向。", conf: 0.6, fresh: 0.3 },
      { id: "e2", src: "本地媒体", url: "kicker.de", time: fmtTime(14), side: "neutral",
        claim: "仅有赛程预告，未涉及首发与伤停。", conf: 0.4, fresh: 0.5 },
    ],
    cycle: [
      { name: "收集", st: "partial", desc: "信源覆盖不足，关键阵容信息缺位。" },
      { name: "加工", st: "completed", desc: "已对现有 3 条情报结构化。" },
      { name: "开发", st: "skipped", desc: "因子缺失过多，未进行加权打分。" },
      { name: "生产", st: "partial", desc: "仅输出数据缺口说明与复扫计划。" },
    ],
    confirmed: [],
    assessments: [
      { id: "a1", text: "现阶段任何方向性结论都不可靠。", t: "assessment", level: "L4", src: "基于信息缺口判断" },
    ],
    alternatives: [],
    nextSteps: [
      "距开赛 24 小时内首发释放后自动复扫。",
      "若仍无官方口径，将维持「信息不足」而不强行给倾向。",
    ],
  };
}

function buildAnalysis(match, question) {
  if (!match) return null;
  if (match.density === "低") return insufficientAnalysis(match);
  return richAnalysis(match, question);
}

// ── product / commerce data ──
const PLANS = [
  { id: "guest", name: "试用", price: "0", unit: "免登录", feature: false,
    items: ["浏览今日赛程", "查看公开倾向标签", "了解研判方法论"], cta: "直接逛逛" },
  { id: "free", name: "注册会员", price: "0", unit: "需邀请码", feature: false,
    items: ["每日 1 次完整研判", "证据链与信源状态", "置信度评级", "问答历史保留 7 天"], cta: "用邀请码注册" },
  { id: "paid", name: "情报通", price: "39", unit: "/ 月", feature: true,
    items: ["无限次完整研判", "因子权重与贝叶斯轨迹", "开赛前自动复扫提醒", "导出研判报告", "优先接入新信源"], cta: "解锁完整研判" },
];

const UNLOCK_FEATURES = [
  "完整证据链 + 逐条信源可信度",
  "因子权重 / 贝叶斯更新轨迹",
  "开赛前 2 小时自动复扫",
  "研判报告导出",
];

// ── admin mock ──
const ADMIN_STATS = [
  { k: "注册用户", v: "1,284" },
  { k: "付费会员", v: "317" },
  { k: "今日研判", v: "2,946" },
  { k: "信源可用率", v: "94%" },
];
const ADMIN_USERS = [
  { name: "qiuhua_01", tier: "paid", joined: "2026-05-02", jobs: 412, expires: "2026-07-02" },
  { name: "data_scout", tier: "paid", joined: "2026-04-18", jobs: 980, expires: "永久" },
  { name: "newbie_fan", tier: "free", joined: "2026-06-14", jobs: 6, expires: "—" },
  { name: "lurker_77", tier: "free", joined: "2026-06-10", jobs: 1, expires: "—" },
];
const ADMIN_INVITES = [
  { code: "QIUHUA-2026", used: 48, cap: 100, by: "运营", st: "active" },
  { code: "EARLYBIRD-7", used: 7, cap: 7, by: "内测", st: "used-up" },
  { code: "VIP-GIFT-3", used: 1, cap: 50, by: "合作", st: "active" },
];

Object.assign(window, {
  QUESTION_PRESETS, FIXTURES, PHASES, SOURCE_POOL,
  buildAnalysis, PLANS, UNLOCK_FEATURES, ADMIN_STATS, ADMIN_USERS, ADMIN_INVITES,
});
