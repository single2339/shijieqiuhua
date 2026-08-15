# 市场对照赛事决策台设计

## 目标

把“世界球花”从一个用户先提问、系统再回答的工具，调整为一套以单场赛事为中心的付费决策台。付费用户点开赛事后，应立即看到：

1. 独立的系统赛前研判：方向、胜平负概率、预测比分带、置信度与关键依据；
2. 独立的市场共识：经过去水处理的胜平负概率、来源数量和采集时间；
3. 系统与市场的明确差异；
4. 根据赛事状态自动变化的赛前、赛中和赛后视图。

非付费用户只可浏览赛程、赛事名称、联赛、开赛时间与赛事状态；不展示方向、比分、概率、市场来源或证据摘要。

## 产品原则

- **结论优先。** 点开比赛后，用户不需要先选“进球数”等标签；全场赛果是默认且唯一的首屏结论。
- **口径独立。** 系统研判仅使用 OSINT 证据和结构化比赛数据；市场共识仅从赔率快照推导。两者不能相互混入，才能成立“系统—市场差异”。
- **市场是参考，不是承诺。** 显示“市场共识参考”，不显示投注入口、跳转链接、收益承诺或下注引导。
- **每个市场数字可追溯。** 展示共识时必须同时有来源数、最新采集时间和原始快照；缺少这些字段时不展示共识概率。
- **赛果与预测分开。** 比赛结束后，“实际比分”永远以赛果身份呈现，不再出现在“公开倾向”标签中。

## 用户与权限

| 用户 | 可见内容 | 不可见内容 |
| --- | --- | --- |
| 访客、免费用户 | 赛程、联赛、开赛时间、已结束状态与实际比分 | 所有研判、比分倾向、概率、市场共识、证据、专项问题答案 |
| 付费用户 | 完整决策台、专项分析、追问、历史回顾和对比 | 无 |

API 必须执行相同的权限规则，不能只依赖前端遮罩。

## 页面设计

### 桌面端：C「市场对照台」

顶部保留轻量导航：赛事、历史、账户。赛事列表改为可收起的左侧抽屉；账户不再占据固定右栏。中心区域是单场决策台。

首屏从上到下按以下顺序排列：

1. **赛事头部**：联赛、开赛时间、状态、主队与客队。
2. **系统研判面板**：`主胜方向`、置信度、预测比分带、主/平/客概率和一句关键依据。
3. **市场共识面板**：主/平/客共识概率、`覆盖 N 个来源`、更新时间和来源状态。
4. **差异面板**：系统首选与市场首选是否一致；显示系统主概率相对市场主概率的百分点差。
5. **关键依据**：默认两条，点击后展开完整分析过程。
6. **专项分析**：总进球、半场、角球、红黄牌、阵容风险。这里不使用“进球数”表示比分预测。
7. **继续追问**：自由输入和预设问题，作为最末级功能。

首屏中的两块核心面板不是两个同权卡片：系统研判使用深绿高对比主面，市场共识使用浅色数据面；差异信息置于它们之间或紧随其后，建立可比较的阅读顺序。

### 移动端

顺序保持“系统研判 → 市场共识 → 差异 → 依据 → 专项分析”。赛事列表成为顶部横向选择器或抽屉，不能压缩首屏的结论。概率在移动端使用三行紧凑条形信息，禁止横向滚动。

### 赛事状态

| 状态 | 首屏内容 |
| --- | --- |
| 未开赛 | 系统研判、市场共识、差异、预计开赛时间和分析快照时间 |
| 进行中 | 保留赛前快照，醒目标注“赛前研判，截至开赛前”；不伪装成实时预测 |
| 已结束 | 实际比分、方向命中、比分命中、赛前系统研判和当时市场快照；深度因子进入赛后回顾 |

## 数据模型

### 系统研判

新增语义边界：`model_prediction` 代表不含市场赔率的 OSINT 预测。它沿用当前 `PredictionResult` 的方向、概率、比分带、置信度、关键因子和不确定性字段，但不能包含 `sporttery_market` 或任何其他赔率字段。

全场比分问题 `全场比分预测是多少？` 是一个赛事的主研判。其他专项问题继续按问题独立缓存和存储，不能覆盖主研判的统计记录。

### 市场快照

每个来源的 1X2 快照统一为：

```python
class MarketSourceSnapshot(BaseModel):
    source_id: str
    display_name: str
    market: Literal["1x2"]
    decimal_odds: OutcomeOdds
    implied_probabilities: OutcomeProbabilities
    observed_at: datetime
    provider_event_id: str
```

`implied_probabilities` 的计算方式为：先将每个十进制赔率转换为 `1 / odds`，再以三项和归一化，从而移除单一来源的庄家边际。

市场共识要求至少三个有效、未过期的来源。共识概率按每个赛果的来源中位数计算后再归一化，避免单一异常盘口主导结论。少于三个来源时：

- 一条来源：显示“单一来源参考”，不显示“市场共识”；
- 两条来源：显示“市场覆盖不足”，不汇总为共识；
- 三条及以上来源：显示“市场共识”，并显示 `覆盖 N 个来源`。

市场快照超过 30 分钟时标记为过期，不参与共识。页面显示最后采集时间与“数据已过期”，而不是用旧数据伪装为当前判断。

### 市场比较

```python
class MarketComparison(BaseModel):
    status: Literal["aligned", "divergent", "limited"]
    model_lead: Literal["home_win", "draw", "away_win"] | None
    market_lead: Literal["home_win", "draw", "away_win"] | None
    lead_delta_points: float | None
    summary: str
```

- `aligned`：系统首选与市场首选相同，且两者主选概率差不超过 7 个百分点；
- `divergent`：首选不同，或主选概率差超过 7 个百分点；
- `limited`：系统信息不足、市场覆盖不足或市场数据过期。

“一致”只表示两个信号方向相同，不能提升系统置信度或写成确定结果。

```python
class MarketConsensus(BaseModel):
    probabilities: OutcomeProbabilities | None
    source_count: int
    observed_at: datetime | None
    coverage_status: Literal["consensus", "single_source", "insufficient", "stale", "unavailable"]
    reason: str

class ActualResult(BaseModel):
    home_score: int
    away_score: int
    outcome: Literal["home", "draw", "away"]
    settled_at: datetime
```

### 决策台响应

付费端使用单一 `MatchDecision` 响应：

```python
class MatchDecision(BaseModel):
    match: OsintMatch
    fixture_status: Literal["scheduled", "live", "finished"]
    model_prediction: PredictionResult | None
    confidence: ConfidenceRating | None
    market_consensus: MarketConsensus | None
    market_sources: list[MarketSourceSnapshot]
    market_comparison: MarketComparison
    evidence_summary: list[IntelligenceFinding]
    updated_at: datetime
    actual_result: ActualResult | None
    review: PostMatchReview | None
```

`MarketConsensus` 除三项概率外，必须提供 `source_count`、`observed_at`、`coverage_status` 与 `reason`。`ActualResult` 只在比赛结束时存在。

## 后端架构与接口

### 数据来源边界

保留现有中国体彩适配器作为一个市场来源。新增一个“已授权多来源赔率数据服务”的适配器边界，不直接抓取 bet365、Pinnacle、Betfair 或其他博彩网站网页。

供应商凭证只存于服务端环境变量；来源名称只有在供应商许可展示时才返回给客户端。无凭证、供应商故障或赛事映射失败时，市场模块返回结构化不可用状态，系统研判仍可正常返回。

### 新接口

`POST /api/football/osint/decisions`

- 权限：已登录且有 `full_analysis` 权益；
- 请求：赛事 provider 身份、provider match ID、主客队、开赛时间、赛事名称；不接受 `question`；
- 行为：读取或生成该赛事的 `fulltime_score` 主研判，读取市场快照并构建 `MatchDecision`；
- 缓存：沿用当前主研判预热窗口；市场快照按独立 TTL 更新；
- 返回：`MatchDecision`。

现有 `POST /jobs` 与 `POST /answer` 保持兼容，后者仅供“专项分析”和自由追问使用。新首屏不再并发调用两个相同问题的端点。

`GET /api/football/osint/history/{job_id}` 扩展为在有赛后数据时返回主研判快照和结算时保存的市场快照，确保历史回顾不可被后续赔率改写。

## 前端组件边界

| 组件 | 责任 |
| --- | --- |
| `DecisionDesk` | 选择赛事后请求 `MatchDecision`，编排状态和加载骨架 |
| `SystemVerdictPanel` | 仅渲染系统方向、比分、概率、置信度和关键依据 |
| `MarketConsensusPanel` | 渲染共识或市场不可用状态；不承担系统结论 |
| `MarketComparisonPanel` | 渲染一致、分歧或信息有限状态 |
| `SpecialistAnalysisPanel` | 承载总进球、半场、角球、红黄牌、阵容风险与自由追问 |
| `FinishedMatchReview` | 渲染实际比分、命中、研判快照与市场快照 |

`App.tsx` 不再保存“默认角球问题”作为主状态。付费用户切换赛事时以赛事 ID 请求决策台；专项问题在用户点击后才创建独立问题任务。

## 加载、异常与空状态

- 缓存命中：先显示完整决策台并标注快照时间；
- 缓存未命中：显示与最终布局同尺寸的结论、市场和差异骨架；
- OSINT 信息不足：系统面明确显示“信息不足，不形成方向结论”，市场仍按其自身可用性呈现为参考；
- 市场不可用：不影响系统面；市场面显示原因，例如“来源覆盖不足”或“市场数据暂不可用”；
- 付费权限失效：清空已加载的研判数据并显示升级入口，避免前端状态泄露；
- 赛事身份无法映射：明确显示“该赛事暂未匹配市场数据”，禁止套用相近名称的盘口。

## 审计、历史与指标

每次主研判保存：系统预测、证据摘要、数据质量、市场来源快照、共识、差异、计算版本和时间。赛后命中率只使用 `fulltime_score` 主研判，保持当前统计原则。

发布后跟踪：

- 付费用户从点击赛事到首个结论可见的中位时长；
- 点开赛事后看到主研判的比例；
- 市场共识可用率及覆盖来源数分布；
- 系统—市场分歧场次比例；
- 赛后方向与比分命中率，按“系统与市场一致 / 分歧”分组，但不宣称因果。

## 验收标准

1. 付费用户点开未开赛赛事后，无需选择问题即可看到全场方向、比分带、系统概率、市场共识和差异状态。
2. 非付费用户无法从 DOM、响应或错误接口获取上述任何研判或市场字段。
3. “全场赛果”是唯一主研判；“总进球”与比分预测采用不同标签和请求。
4. 少于三条新鲜市场来源时不渲染“市场共识”。
5. 系统概率的生成代码路径不读取市场概率；比较模块只在两者生成后运行。
6. 已结束赛事首屏优先展示实际比分和命中状态，并能读取当时保存的市场快照。
7. 所有市场来源均有来源名、原始赔率、采集时间和去水后的概率；来源映射不确定时不展示该来源。
