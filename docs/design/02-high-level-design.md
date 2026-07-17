# OSINT Network 概要设计文档

## 1. 系统分层架构

```
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 5: 表现层 (Presentation)                                      │
│  React 19 SPA — 组件树 → MapView/MessageFeed/LayerPanel/分析面板     │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 4: API 网关层 (API Gateway)                                   │
│  FastAPI — 37+ REST 端点 + WebSocket — CORS/Auth/限流/Cache-Control  │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 3: 业务逻辑层 (Business Logic)                                │
│  Agent 系统 (25+ agents) — IntelItem构建 — 12分析引擎 — 报告生成     │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 2: 数据处理层 (Data Processing)                               │
│  翻译/摘要/LLM分类/关键词分类/地理定位/贝叶斯评分/Union-Find合并     │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 1: 数据层 (Data)                                              │
│  Bronze JSON (按日期分区) — SQLite 索引 — Merge Index — 嵌入索引     │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. 模块划分

### 2.1 后端模块树

```
backend/
├── main.py                    # FastAPI 入口 — 生命周期、中间件、全部路由、缓存
├── models.py                  # Pydantic 数据模型 — 50+ 类型定义
├── llm_config.py              # LLM 客户端配置（DeepSeek API）
├── bronze_reader.py           # Bronze JSON 文件扫描器
├── indexer.py                 # SQLite 全文索引（增量和全量构建）
├── merger.py                  # Union-Find 内容合并引擎
├── seed_data.py               # Demo 数据生成器（90+ 模板）
├── osint_sources.py           # 数据源目录（可信度评分）
├── opencode_adapter.py        # OpenCode 代理适配器
│
├── auth/                      # 认证模块
│   ├── routes.py              # 注册/登录/Token 刷新
│   ├── admin_routes.py        # 管理员路由
│   ├── service.py             # JWT Token 服务
│   └── tracking.py            # 用户活动追踪
│
├── agents/                    # Agent 编排系统
│   ├── base.py                # Agent 基类 + Callbacks
│   ├── registry.py            # Agent 注册表
│   ├── config.py              # Agent 模式配置
│   ├── models.py              # AgentTask 模型
│   ├── skill.py               # Skill 加载器
│   ├── collectors/            # 采集器 agents (4个)
│   │   ├── api_collectors.py  # CISA/USGS/OpenSky
│   │   ├── rss_collector.py
│   │   └── social_collectors.py
│   ├── processors/            # 处理器 agents (5个)
│   │   ├── pipeline.py        # 流水线编排
│   │   ├── translation.py
│   │   ├── summarization.py
│   │   ├── classification.py
│   │   ├── location_extraction.py
│   │   └── document_quality.py
│   ├── intelligence/          # 情报分析 agents (4个)
│   │   ├── qa_analyst.py
│   │   ├── report_writer.py
│   │   ├── super_analyst.py
│   │   └── interpretation.py
│   ├── analysis/              # 分析 agents (6个)
│   │   ├── timeline.py
│   │   ├── entity_graph.py
│   │   ├── corroboration.py
│   │   ├── anomaly_detector.py
│   │   ├── risk_heatmap.py
│   │   └── gap_analyzer.py
│   └── system/                # 系统 agents (3个)
│       ├── orchestrator.py
│       ├── indexer.py
│       └── merger.py
│
├── processors/                # 核心处理引擎
│   ├── analysis.py            # 7 大分析函数 + 事件聚类 + 预警 + 态势简报
│   ├── llm_classifier.py      # LLM 分类器（DeepSeek，12层 + 消歧 + 地点提取）
│   ├── classifier.py          # 关键词分类器（12组规则，回退方案）
│   ├── location.py            # 地理定位（城市级数据库 + 来源推断）
│   ├── progress.py            # 超级分析进度追踪
│   └── embedding_index.py     # 嵌入向量语义索引
│
├── collectors/                # Horizon 采集桥接
│   ├── horizon_bridge.py      # 翻译→摘要→LLM分类→写入
│   └── horizon/               # 采集器实现
│       └── scrapers/          # RSS/Reddit/HN/Telegram/GitHub
│
└── websocket/                 # WebSocket 管理
    └── manager.py             # 频道订阅/广播
```

### 2.2 前端模块树

```
frontend/src/
├── App.tsx                    # 根组件 — 布局、路由、全局状态
├── api.ts                     # HTTP API 客户端（fetch 封装）
├── types.ts                   # TypeScript 类型 + LAYER_META (12层中文标签+颜色)
├── index.css                  # CSS 自定义属性（暖色调设计系统）
│
├── components/
│   ├── MapView.tsx            # MapLibre GL 地图（天地图瓦片）
│   ├── MessageFeed.tsx        # 情报信息流（虚拟滚动）
│   ├── IntelCard.tsx          # 情报卡片（展开/收起详情）
│   ├── LayerPanel.tsx         # 图层筛选面板（12层 SVG 图标 + 颜色标识）
│   ├── AskPanel.tsx           # AI 问答面板（流式输出）
│   ├── ReportPanel.tsx        # 态势报告生成面板
│   ├── StatsPanel.tsx         # 统计图表面板
│   ├── SourcePanel.tsx        # 数据源可信度面板
│   ├── MobileMenu.tsx         # 移动端汉堡菜单（< 767px）
│   ├── StatusDot.tsx          # 系统状态指示灯（绿/黄/红）
│   ├── IntelAnalysisPanel.tsx # 情报分析面板容器（Tab 切换 7 种视图）
│   ├── SuperAnalysisPanel.tsx # 超级分析面板（贝叶斯+网络搜索）
│   ├── SuperAnalysisSidebar.tsx
│   ├── LoginPage.tsx          # 登录页面
│   ├── RegisterPage.tsx       # 注册页面
│   ├── AdminPanel.tsx         # 管理面板
│   ├── ErrorBoundary.tsx      # 错误边界（React 异常捕获）
│   └── analysis/              # 分析子视图组件
│       ├── TimelineView.tsx
│       ├── EntityGraphView.tsx
│       ├── CorroborationView.tsx
│       ├── AnomalyView.tsx
│       ├── RiskHeatmapView.tsx
│       ├── GapAnalysisView.tsx
│       └── AIInterpretBadge.tsx
│
├── hooks/
│   └── useDashboardData.ts    # Dashboard 数据轮询 Hook（10s 间隔 + 缓存去重）
│
└── icons/                     # 12 图层 SVG 图标组件（React 函数组件）
    ├── NatureIcon.tsx, EconomyIcon.tsx, FinanceIcon.tsx
    ├── PoliticsIcon.tsx, MilitaryIcon.tsx, AviationIcon.tsx
    ├── TechnologyIcon.tsx, SocietyIcon.tsx, EnergyIcon.tsx
    ├── AgricultureIcon.tsx, HealthIcon.tsx, CyberIcon.tsx
```

## 3. API 路由设计

### 3.1 路由总览

| 方法 | 路径 | 认证 | 用途 |
|------|------|------|------|
| GET | `/api/dashboard` | 否 | 主仪表盘数据（分页，支持 start_date/end_date/date/page/page_size） |
| GET | `/api/health` | 否 | 健康检查（返回 bronze_docs 总数） |
| GET | `/api/stats` | 否 | 聚合统计（趋势、来源矩阵、地理分布、关键词 Top30） |
| POST | `/api/collect` | 是 | 手动触发采集（可选 hours 参数） |
| GET | `/api/collect/status` | 否 | 采集任务状态（idle/running/completed/error） |
| POST | `/api/merge` | 是 | 触发内容合并（清空所有缓存） |
| POST | `/api/reclassify` | 是 | 重新分类已有文档（支持 force + use_llm 参数） |
| POST | `/api/reindex` | 是 | 增量更新 SQLite 索引 |
| POST | `/api/ask` | 否 | AI 问答（基于 IntelItem 数据，支持 layer/date 过滤） |
| POST | `/api/report` | 否 | 生成态势报告（支持 topic/country/layer/days 参数） |
| GET | `/api/super-analysis/progress` | 是 | 超级分析实时进度（按用户和 request_id 隔离） |
| GET | `/api/analysis/timeline` | 否 | 时间线分析（按日期聚合 + 图层分布） |
| GET | `/api/analysis/entities` | 否 | 实体图谱（Top50 实体 + 共现边） |
| GET | `/api/analysis/corroboration` | 否 | 交叉验证矩阵（基于事件簇的源对重叠度） |
| GET | `/api/analysis/anomalies` | 否 | 异常检测（Z-Score > 1.5，4级严重度） |
| GET | `/api/analysis/risk-heatmap` | 否 | 风险热力图（按国家，综合密度+置信度+图层风险权重） |
| GET | `/api/analysis/gaps` | 否 | 覆盖缺口分析（主题缺口/地区缺口/时间缺口/单源占比） |
| GET | `/api/analysis/brief` | 否 | 结构化态势简报（核心发现+确认事实+替代解释+待核查项） |
| GET | `/api/analysis/events` | 否 | 事件聚类（基于 Token Jaccard + 国家/图层/时间相似度） |
| GET | `/api/analysis/warnings` | 否 | 预警指标（I&W 框架，按严重度排序） |
| POST | `/api/analysis/interpret` | 否 | AI 解读分析结果 |
| GET | `/api/collect/usgs` | 是 | USGS 地震数据采集（M2.5+，7天内） |
| GET | `/api/collect/cisa` | 是 | CISA 已知被利用漏洞列表 |
| GET | `/api/collect/opensky` | 是 | OpenSky 航班追踪统计 |
| POST | `/api/process/translate` | 是 | 文本翻译 |
| POST | `/api/process/summarize` | 是 | 文本摘要 |
| POST | `/api/process/classify` | 是 | 图层分类 |
| POST | `/api/process/locate` | 是 | 地理定位 |
| POST | `/api/process/document-quality` | 是 | 文档呈现质量评估（不判断主张真值） |
| POST | `/api/process/pipeline` | 是 | 处理流水线（翻译→摘要→分类→定位，可选文档质量） |
| GET | `/api/skills` | 否 | 可用 Skills 列表 |
| GET | `/api/agent/status` | 否 | Agent 系统状态（按类型汇总 + Skills 列表） |
| WS | `/ws/{channel}` | — | WebSocket 实时推送（支持多频道） |
| POST | `/api/intel/ask` | 是 | 情报问答（OpenCode Agent + 本地回退） |
| POST | `/api/intel/report` | 是 | 情报报告（OpenCode Agent + 本地回退） |
| POST | `/api/intel/super-analysis` | 是 | 超级分析（关系分类→固定 LR 贝叶斯更新→结论生成） |
| POST | `/api/intel/interpret` | 是 | AI 解读（OpenCode Agent + 本地回退） |
| POST | `/api/intel/build-embedding-index` | 是 | 构建嵌入向量索引 |
| POST | `/api/auth/register` | 否 | 用户注册 |
| POST | `/api/auth/login` | 否 | 用户登录 |
| POST | `/api/auth/refresh` | 否 | Token 刷新 |
| GET | `/api/admin/users` | 是 | 用户列表（管理员） |

### 3.2 中间件管道

```
Request
  → Body Size Limit (2MB 硬限制，超限返回 413)
  → Auth (JWT Token 验证，支持 Cookie/Bearer Header，Refresh Token 自动续期)
  → Rate Limit (滑动窗口，GET: 300 req/min, POST: 60 req/min)
  → Cache-Control Header 注入
  → Route Handler
```

**公开路径**（跳过认证）：`/api/health`, `/api/auth/*`, `/api/admin/*`, `/api/dashboard`, `/api/stats`, `/api/analysis/*`

## 4. 核心数据模型

### 4.1 情报条目 (IntelItem)

```python
class IntelItem(BaseModel):
    id: str                          # 唯一标识
    title: str                       # 标题
    summary: str                     # 摘要
    layer: IntelLayer                # 情报图层（12 枚举值）
    location: GeoPoint               # 经纬度 (lat: -90~90, lng: -180~180)
    location_name: str               # 地点名称
    country: str                     # 国家
    confidence: float                # 置信度 [0.0, 1.0]
    verdict: Verdict                 # 验证状态: verified / false / uncertain
    bayesian_trace: list[float]      # 贝叶斯后验概率追踪序列
    evidence_count: int              # 独立证据数
    sources: list[str]               # 来源列表（合并后的多源）
    source_system: str               # 主来源系统
    captured_at: str                 # 采集时间 (ISO 8601)
    url: str                         # 原始链接
    bayesian_method: str             # 贝叶斯方法名称
    bayesian_prior_quality: str      # 先验质量等级
    bayesian_prior_class: str        # 先验来源类别
    bayesian_evidence_items: list[BayesianEvidence]
```

### 4.2 贝叶斯证据项

```python
class BayesianEvidence(BaseModel):
    name: str           # 证据名称
    quality: str        # 证据质量: high / medium / low
    lr: float           # 似然比 (>1 支持, <1 反对)
    dep_discount: float # 依赖折扣 [0,1]，1=完全独立
    direction: str      # 方向: support / oppose
```

### 4.3 结构化研判输出 (SituationBriefResult)

```python
class SituationBriefResult(BaseModel):
    summary: str                          # 总体摘要
    intelligence_level: ConfidenceAssessment  # 整体情报等级
    source_count: int                     # 来源总数
    core_findings: list[CoreFinding]      # 核心发现
    confirmed_facts: list[IntelligenceStatement]  # 确认事实
    assessments: list[IntelligenceStatement]     # 分析判断
    alternative_explanations: list[AlternativeExplanation]  # 替代解释
    pending_verification: list[PendingVerification]          # 待核查项
    key_judgments: list[KeyJudgment]      # 关键判断（含影响评估、时效、不确定性）
    evidence: list[BriefEvidence]         # 证据索引
    contradictions: list[BriefIssue]      # 矛盾与问题
    collection_gaps: list[BriefIssue]     # 采集缺口
    recommended_tasks: list[CollectionTask]  # 建议采集任务
```

### 4.4 关键判断 (KeyJudgment)

```python
class KeyJudgment(BaseModel):
    id: str
    judgment: str              # 判断内容
    confidence_level: str      # L1/L2/L3/L4
    confidence_score: float    # 数值置信度 [0,1]
    impact: str                # 影响评估: 战略/行业/区域/战术
    time_sensitivity: str      # 处置时效: 立即/24h/72h
    support_count: int         # 支撑样本数
    evidence_ids: list[str]    # 支撑证据 ID
    uncertainties: list[str]   # 不确定性说明
```

### 4.5 置信度评估 (ConfidenceAssessment)

```python
class ConfidenceAssessment(BaseModel):
    level: str                     # L1/L2/L3/L4
    label: str                     # 确认/高可信/中可信/推测
    rationale: str                 # 评级理由
    independent_source_count: int  # 独立来源数
    evidence_count: int            # 证据条目数
    evidence_ids: list[str]        # 支撑证据 ID
```

## 5. 关键算法

### 5.1 内容合并 (Union-Find, merger.py)

```
输入: Bronze JSON 文档列表
输出: MergeIndex (group_id → [doc_ids] + sources[] + source_url)

算法:
1. 初始化 UnionFind，每个 doc_id 为一个独立集合
2. 遍历文档对 (i, j):
   a. 若 source_url 相同 → union(document_i, document_j)
   b. 若 content_sha256 相同 → union(document_i, document_j)
   c. 若 归一化标题相同（去标点、小写、trim） → union(document_i, document_j)
3. 提取所有连通分量 groups
4. 每个 group:
   - primary_doc → 选择 captured_at 最早的文档
   - sources → 去重合并所有文档的 source_system
   - source_url → 取主文档的 URL
5. 序列化为 bronze_storage/_merge_index.json
```

### 5.2 事件聚类 (analysis.py: generate_event_clusters)

```
输入: IntelItem 列表, limit=20
输出: EventCluster 列表

算法（贪心单遍聚类）:
1. 按 item_score（综合 置信度+来源数+证据数+图层权重）降序排列
2. 对每个 item:
   token = _claim_tokens(item)  # 中英文 token 提取 + 停用词过滤
   对每个已有 cluster:
     similarity = Jaccard(token, cluster.tokens)
     same_country = (item.country in cluster.countries) → +0.12
     same_layer = (item.layer in cluster.layers) → +0.08
     date_distance ≤ 1 → +0.08
     date_distance > 3 → 直接拒绝 (score=0)
     score = similarity + country_bonus + layer_bonus + date_bonus
   若最佳 score ≥ 0.24 → 加入该 cluster
   否则 → 创建新 cluster
3. 按 (item数, 独立来源数, 总score) 降序排列
```

### 5.3 置信度评估 (analysis.py: _confidence_assessment)

```
输入: 支撑 items 列表, 证据 ID 列表
输出: ConfidenceAssessment

算法:
1. 收集独立来源名称（去重 source_system）
2. independent_count = len(unique_sources)
3. avg_confidence = mean(item.confidence for item in items)
4. 判定规则:
   independent_count ≥ 3 → L1, "确认"
     理由: "{n} 个独立来源交叉支撑，符合三方验证标准"
   independent_count == 2 → L2, "高可信"
     理由: "2 个独立来源支撑，可信度较高但尚未达到三方验证"
   independent_count == 1 AND avg_confidence ≥ 0.6 → L3, "中可信"
     理由: "1 个可靠来源支撑，可作为中可信线索"
   其他 → L4, "推测"
     理由: "证据不足或主要依赖间接证据，只能作为推测"
5. confidence_score = base[level] × 0.75 + avg_confidence × 0.25
   base = {L1: 0.90, L2: 0.76, L3: 0.60, L4: 0.38}
```

### 5.4 风险热力图 (analysis.py: compute_risk_heatmap)

```
输入: IntelItem 列表
输出: RegionRisk 列表（按 risk_score 降序）

算法（逐国家计算）:
1. country_items[country] = [items in that country]
2. max_density = max(len(items) for items in country_items.values())
3. 对每个 country:
   density_norm = len(items) / max_density  (min-max 归一化)
   avg_conf = mean(item.confidence)
   layer_risk = Σ(LAYER_RISK_WEIGHTS[layer] × count/total)  (按图层加权)
   risk_score = density_norm × 0.3 + avg_conf × 0.3 + layer_risk × 0.4
```

### 5.5 异常检测 (analysis.py: detect_anomalies)

```
输入: IntelItem 列表
输出: AnomalyEvent 列表

算法（Z-Score）:
1. 按 (layer, date) 聚合计数
2. 计算每层的均值 mean 和标准差 std
3. 对每个 (layer, date):
   z = (count - mean) / max(std, 1.0)
   若 |z| > 1.5 → 标记异常:
     |z| ≥ 3.0 → critical
     |z| ≥ 2.5 → high
     |z| ≥ 2.0 → medium
     否则    → low
```

### 5.6 预警指标生成 (analysis.py: generate_warning_indicators)

```
输入: IntelItem 列表 + 事件聚类结果
输出: WarningIndicator 列表

规则:
1. 事件级预警: 高敏感图层 (military/cyber/politics/finance/energy/health)
   事件簇达到 L1/L2 → 生成预警，严重度按图层+置信度判定
2. 主题集中预警: 单个高敏感图层样本占比 ≥ 35% → 标记 watch
3. 单源线索预警: 高敏感情报中单源支撑占比过高 → 建议优先核查
4. 整体等级: 取所有指标中最高严重度 = critical/high/watch/normal
```

## 6. 双层分类系统

### 6.1 LLM 分类器（主分类器 — llm_classifier.py）

- **模型**: DeepSeek Chat (`deepseek-chat`)
- **输入**: title + content（截断至 3000 字符）
- **输出 JSON**: `{"layer": "<key>", "country": "<name>", "city": "<name>"}`
- **SYSTEM_PROMPT 设计**:
  - 12 层完整定义（每层含英文 key + 中文领域描述）
  - 消歧规则（12 条，覆盖能源政策/市场、贸易政策/操作、航天/民航、军事/民用无人机、网络攻击归属等）
  - 地点提取三重优先级：
    1. 事件发生地点
    2. 实体所在地（公司总部、组织驻地）
    3. 全球（无法确定时回退）

### 6.2 关键词分类器（回退分类器 — classifier.py）

- 12 组关键词规则，每组 20-50 个中英文关键词
- 加权匹配策略: 标题中的关键词权重 ×3
- 自动回退条件: LLM 超时 / API 错误 / JSON 解析失败

### 6.3 分类数据流

```
_collect_item(text) 或 _build_items(doc)
  │
  ├── horizons_metadata.layer 已存在 (采集时LLM分类)
  │   └── 直接使用（跳过二次分类）
  │
  └── 不存在 → classify(text)
       ├── 优先: classify_with_llm() → 返回 (layer, country, city)
       │   └── 失败 → keyword_classify() → 返回 layer
       └── _get_layer(doc): 读取 layer 值 → IntelLayer 枚举 → 失败则回到 classify()
```

## 7. 前端-后端交互

### 7.1 Dashboard 数据轮询

```
前端 (useDashboardData hook, 10s 间隔)
  │
  ├── GET /api/dashboard?page=1&page_size=100
  │     │
  │     ├── 缓存命中 (300s TTL) → 即时返回 ← 预热已构建
  │     └── 缓存未命中
  │           └── run_in_executor(_build_items)
  │                 ├── indexer.get_all() → 全量文档
  │                 ├── load_merge_index() → 合并分组
  │                 ├── _make_item() × N
  │                 │     ├── extract_location_with_fallback()
  │                 │     ├── _get_layer() → classify()
  │                 │     └── _collection_confidence_from_sources()
  │                 └── 分页 + _build_dashboard_data()
  │
  └── 状态更新 → React setState → 组件重渲染
```

### 7.2 超级分析请求流

```
POST /api/super-analysis {question, start_date, end_date, skills}
  │
  ├── init_progress(request_id) → 进度追踪
  │
  ├── SuperAnalystAgent.run()
  │     ├── 搜索相关 IntelItem → 贝叶斯评分
  │     ├── Web 搜索（可选）
  │     ├── LLM 深度推理 → 结构化分析报告
  │     └── 返回 {analysis, relevant_items, web_results}
  │
  ├── [intel 变体] → _run_local_super_analysis_enhancement()
  │     └── osint-core skill 二次复核 → 附加增强段
  │
  └── 返回 SuperAnalysisResponse
```

### 7.3 WebSocket 实时推送

```
ws://host/ws/collection
  │
  ├── OrchestratorAgent.start_collection_loop()
  │     └── 采集进度 → ws_manager.broadcast(channel, event_type, data)
  │
  ├── 事件类型: status_change, progress_update, item_collected, error
  └── 前端实时更新 StatusDot + 采集进度条
```

## 8. 缓存策略

### 8.1 三层缓存架构

| 层级 | 存储位置 | TTL | Key 格式 | 内容 |
|------|---------|-----|---------|------|
| Master List | `_master_list_cache: dict` | 300s | `_items:{start}\|{end}\|{date}` | IntelItem 全量列表 |
| Dashboard Page | `_dashboard_cache: dict` | 300s | `{start}\|{end}\|{date}\|{page}\|{page_size}` | DashboardData |
| Analysis Snapshot | `_dashboard_cache: dict` + `asyncio.Lock` | 300s | `analysis_brief\|{params}` / `analysis_corroboration\|{params}` 等 | 分析结果对象 |

### 8.2 缓存失效策略

- **被动失效**: TTL 过期自动清除
- **主动失效**: 以下操作清空所有缓存
  - `POST /api/merge`
  - `POST /api/reclassify`
  - `POST /api/reindex`
  - 采集任务完成后

### 8.3 缓存预热

启动时自动构建：
1. `_items:|||` — 全量 item 列表（最昂贵操作，~102 秒首次）
2. `||||1|200` / `||||1|100` — 热点页面变体

预热在 `run_in_executor` 中异步执行，不阻塞服务启动。

## 9. Agent 编排系统

### 9.1 Agent 类型

| 类型 | 数量 | 用途 |
|------|------|------|
| `collector` | 4 | RSS、社交媒体、API 数据采集 |
| `processor` | 5 | 翻译、摘要、分类、地理定位、贝叶斯评分 |
| `intelligence` | 4 | QA 分析、报告撰写、超级分析、结果解读 |
| `analysis` | 6 | 时间线、实体图、交叉验证、异常检测、风险热力、缺口分析 |
| `system` | 3 | 编排调度、索引管理、内容合并 |

### 9.2 Agent 生命周期

```
创建 → AgentRegistry.create(id) → agent.run(task)
  │
  ├── 状态机: idle → running → completed / failed
  ├── 事件广播: on_event / on_status_change / on_error → WebSocket
  ├── Skill 注入: task.skills → SkillLoader.load_for_task()
  └── 结果返回: AgentResult {data, status, duration}
```

### 9.3 OrchestratorAgent

系统级编排 Agent，管理：
- **采集循环**: 定时触发采集任务，通过 WebSocket 广播进度
- **合并循环**: 每日 03:00 UTC 自动执行内容合并
