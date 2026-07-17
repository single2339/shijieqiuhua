# OSINT Network 详细设计文档

## 1. 数据存储层

### 1.1 Bronze Storage 文件结构

```
bronze_storage/
├── 2026-06-12/
│   ├── Reuters/
│   │   └── <uuid>.json
│   ├── Xinhua/
│   │   └── <uuid>.json
│   └── ...
├── 2026-06-11/
├── _index.db               # SQLite FTS 索引
├── _merge_index.json       # 内容合并索引
├── _queue.db               # 采集队列数据库
└── embedding_index/        # 嵌入向量索引目录
```

### 1.2 Bronze JSON 文档格式

```json
{
  "raw_document_id": "uuid-string",
  "captured_at": "2026-06-12T08:30:00+00:00",
  "source_system": "Reuters",
  "source_url": "https://www.reuters.com/article/...",
  "collection_method": "rss",
  "text": "全文内容...",
  "content_sha256": "abc123...",
  "extensions": {
    "summary": "AI 生成摘要文本",
    "horizon_title": "原始标题",
    "horizon_metadata": {
      "feed_name": "Reuters",
      "feed_url": "https://...",
      "layer": "economy",
      "location_country": "中国",
      "location_city": "上海",
      "translated": true,
      "translated_from": "en",
      "classification_method": "llm"
    }
  }
}
```

### 1.3 Merge Index 结构 (`_merge_index.json`)

```python
@dataclass
class MergedDocumentInfo:
    doc_id: str
    source: str
    captured_at: str

@dataclass
class MergedGroup:
    group_id: str
    primary_doc_id: str
    documents: list[MergedDocumentInfo]
    sources: list[str]          # 去重合并
    source_url: str
    merged_at: str

@dataclass
class MergeIndex:
    groups: list[MergedGroup]
    total_groups: int
    total_docs: int
    generated_at: str
```

### 1.4 SQLite 索引 Schema

```sql
CREATE TABLE bronze_index (
    raw_document_id TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    layer TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    extensions_json TEXT NOT NULL DEFAULT '{}',
    file_path TEXT NOT NULL DEFAULT '',
    body_size INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_captured_at ON bronze_index(captured_at);
CREATE INDEX idx_layer ON bronze_index(layer);
CREATE INDEX idx_country ON bronze_index(country);
CREATE INDEX idx_sha256 ON bronze_index(content_sha256);
CREATE INDEX idx_source ON bronze_index(source_system);
```

关键方法：
- `build_index()` — 全量扫描 bronze JSON 文件并写入 SQLite
- `incremental_update()` — 仅索引新文件（基于 file_path 比对）
- `query(start_date, end_date, layer, country, limit)` — 条件查询返回 BronzeDocument 列表
- `get_all()` — 返回全部索引文档
- `get_available_dates()` — 返回所有有数据的日期
- `count()` — 返回索引文档总数

## 2. 采集流水线

### 2.1 Horizon Bridge (`collectors/horizon_bridge.py`)

```python
# 数据源配置
_DEFAULT_RSS_FEEDS: list[RSSSourceConfig]  # 30+ 国际 + 中文 RSS 源
_HN_CONFIG: HackerNewsConfig               # HackerNews top/best/new
_REDDIT_CONFIG: RedditConfig               # 5+ subreddits
_TELEGRAM_CONFIG: TelegramConfig           # 3+ 频道
_GITHUB_CONFIG: GitHubSourceConfig         # 安全/情报仓库

# 处理流水线
async def run_horizon_collection(hours: int = 48) -> dict:
    # 1. 并行运行 5 个采集器
    # 2. 对每个 ContentItem:
    #    a. _translate_item() → 非中文内容翻译为中文
    #    b. _summarize_item() → LLM 生成 200 字摘要
    #    c. _classify_item() → LLM 分类 + 地点提取
    #    d. _to_raw_document() → 转换格式 + 写入 Bronze JSON
    # 3. 返回统计: {total, translated, classified, written}

async def _translate_item(item: ContentItem) -> str:
    # 检测语言 → 非中文则调用 translate_text()

async def _summarize_item(text: str) -> str:
    # 调用 _summarize_with_llm() 生成 200 字中文摘要

async def _classify_item(title: str, text: str) -> tuple[IntelLayer, str, str]:
    # 调用 classify_with_llm() 返回 (layer, country, city)

def _to_raw_document(item: ContentItem, ...) -> RawDocument:
    # 构建 RawDocument，包含 extensions.horizon_metadata
    # 写入 bronze_storage/{date}/{feed_name}/{uuid}.json
```

### 2.2 采集器实现 (`collectors/horizon/scrapers/`)

| 采集器 | 数据源 | 方法 |
|--------|--------|------|
| `RSSScraper` | RSS/Atom feeds | `scrape(sources)` — 解析 XML → ContentItem 列表 |
| `HackerNewsScraper` | HN API | `scrape(config)` — 获取 top/best/new stories |
| `RedditScraper` | Reddit JSON API | `scrape(config)` — 获取 subreddit 热门帖子 |
| `TelegramScraper` | Telegram Web | `scrape(config)` — 获取频道最新消息 |
| `GitHubScraper` | GitHub API | `scrape(config)` — 获取仓库 trending/commits |

### 2.3 中文 RSS 源配置

通过 RSSHub (Docker, `127.0.0.1:1200`) 支持：
- 微博热搜 `http://127.0.0.1:1200/weibo/search/hot`
- CLS 财经电报 `http://127.0.0.1:1200/cls/telegraph`
- 早报 RSS `http://127.0.0.1:1200/zaobao/realtime/china`

## 3. 处理引擎

### 3.1 LLM 分类器 (`processors/llm_classifier.py`)

```python
MAX_INPUT_LENGTH = 3000
MAX_RETRIES = 2
CLASSIFY_DELAY = 0.3  # 请求间隔秒数

async def classify_with_llm(title: str, content: str) -> tuple[IntelLayer, str, str]:
    """
    输入: title + content (截断至 3000 字符)
    输出: (IntelLayer 枚举值, country 中文名, city 中文名)

    处理流程:
    1. 截断 content 至 MAX_INPUT_LENGTH
    2. 构建 messages = [{"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Title: {title}\n\nContent: {content}"}]
    3. POST {LLM_BASE_URL}/chat/completions
       - model: LLM_MODEL (deepseek-chat)
       - temperature: 0.1
       - max_tokens: 150
       - response_format: {"type": "json_object"}
    4. 解析 JSON → 提取 layer/country/city
    5. 验证 layer 在 IntelLayer 枚举值中
    6. 失败回退 → keyword_classify() + extract_location_with_fallback()
    7. 重试: 最多 2 次，间隔 0.3s
    """

SYSTEM_PROMPT = """
You are an intelligence classification and geolocation expert.
Given a piece of intelligence text, do TWO things:
1. Classify the text into EXACTLY ONE of 12 categories
2. Extract geographic location following priority rules

Categories (12 layers with descriptions):
- nature: Natural disasters, climate, weather, environment, ecology...
- economy: Business, companies, manufacturing, supply chains, logistics...
- finance: Financial markets, currencies, interest rates, stocks, bonds...
- politics: Elections, governance, diplomacy, international relations...
- military: Armed forces, weapons, defense, wars, combat, military exercises...
- aviation: Civil aviation, airlines, aircraft, airports, air travel...
- technology: AI, semiconductors, biotech, space exploration, satellites...
- society: Social movements, protests, education, culture, sports, migration...
- energy: Oil, gas, renewables, solar, wind, nuclear power, critical minerals...
- agriculture: Food security, crop production, grain trade, fisheries, livestock...
- health: Pandemics, vaccines, disease outbreaks, healthcare systems...
- cyber: Cyber attacks, data breaches, hacking, ransomware, digital sovereignty...

Disambiguation rules (12 rules):
- Energy POLICY (OPEC decisions, energy sanctions) → energy.
  Energy MARKETS (oil futures, LNG spot prices) → finance.
- Trade POLICY (tariffs, trade wars, FTAs, customs rules) → politics.
  Trade/export OPERATIONS (company shipments, factory orders) → economy.
- Space exploration, satellites, rockets, NASA, SpaceX launches → technology.
  Civil airlines, airports, Boeing/Airbus → aviation.
- Military drones/combat UAVs → military. Civilian drones/delivery drones → technology.
- AI research AND AI industry (LLMs, ChatGPT, AI chips, AI startups) → technology.
- Pandemic outbreak, vaccine development, WHO declarations → health.
  Healthcare access as social/political issue → politics.
- Cyber attacks on military targets → military.
  Civilian hacking, data breaches, ransomware → cyber.
- Supply chain disruption, factory output, shipping rates → economy.
- Food PRICES and agricultural COMMODITY markets → finance.
  Crop production, harvests, food security → agriculture.
- If multiple categories match, pick the MOST SPECIFIC one.

Location extraction rules (CRITICAL):
- Priority 1 — Incident location: specific event/action location
  Examples: '俄军在顿涅茨克推进' → country='乌克兰', city='顿涅茨克'
- Priority 2 — Entity location: main entity's base/home country
  Examples: '太初电子获新一轮融资' → country='中国', city='无锡'
- Priority 3 — Fallback: only if neither can be determined
  Example: 'Global climate change report released' → country='全球', city=''
- Be specific when possible: prefer '上海' over '中国'
- Use your knowledge of well-known entities to determine their location
- For country names, use the short Chinese name (中国, 美国, 日本, 英国, etc)
"""
```

### 3.2 关键词分类器 (`processors/classifier.py`)

```python
def classify(text: str) -> IntelLayer:
    """
    回退分类器 — 基于 12 组关键词的加权匹配。

    算法:
    1. 分离标题（首行）和正文
    2. 对 12 组规则分别计算匹配分数:
       title_score = Σ(match in title) × 3
       body_score = Σ(match in body)
       total_score = title_score + body_score
    3. 返回最高分数对应的 IntelLayer
    4. 平局时按预定义优先级: military > cyber > politics > finance > energy
       > health > aviation > agriculture > economy > technology > society > nature
    """

_LAYER_RULES: list[tuple[IntelLayer, list[str]]] = [
    (IntelLayer.NATURE, [
        "climate", "weather", "flood", "drought", "earthquake", "wildfire",
        "hurricane", "typhoon", "tsunami", "volcano", "storm",
        "气候", "天气", "干旱", "洪水", "地震", "野火", "森林火灾",
        "飓风", "台风", "海啸", "火山", "风暴", "碳排放", "生态系统",
    ]),
    (IntelLayer.ECONOMY, [
        "company", "corporation", "factory", "manufacturing", "supply chain",
        "logistics", "shipping", "retail", "production", "industry",
        "公司", "企业", "工厂", "制造", "供应链", "物流", "零售", "产业",
    ]),
    # ... 共 12 组，每组 20-50 个中英文关键词
]
```

### 3.3 地理定位器 (`processors/location.py`)

```python
def extract_location_with_fallback(
    text: str,
    source_name: str,
    doc: BronzeDocument | None = None
) -> tuple[str, str, float, float]:
    """
    三层回退定位策略 → (country, city, lat, lng)

    Layer 1 — 城市级精确匹配:
      _CITIES[] 包含 150+ 城市，每项:
        {country, city, variants: [中文名, 英文名, ...], lat, lng}
      遍历城市 → 子串匹配 variant → 返回 country/city/lat/lng

    Layer 2 — 国家级模糊匹配:
      _COUNTRIES[] 包含 60+ 国家:
        {country, variants: [中文名, 英文名, 简称, ...]}
      遍历国家 → 匹配 → 返回 country + (0, 0) 坐标

    Layer 3 — 来源推断回退:
      _SOURCE_COUNTRY_MAP:
        - 含 "Reuters"/"BBC"/"Guardian" → country="英国"
        - 含 "Xinhua"/"People"/"China" → country="中国"
        - 含 "CNN"/"NYT"/"Washington" → country="美国"
        - 含 "Kyodo"/"NHK"/"Asahi" → country="日本"
        - 含 "RT"/"TASS"/"Sputnik" → country="俄罗斯"
      如 source_name 包含这些关键词 → 返回对应国家

    台湾处理 (CRITICAL):
      _TAIWAN_COUNTRY = "中国台湾省"
      _TAIWAN_COUNTRY_ALIASES = {"台湾", "台湾省", "中国台湾", "taiwan", ...}
      _TAIWAN_CITY_NAMES = {"台北", "高雄", "基隆", "taipei", ...}
      所有台湾相关地点自动规范化为 (lat=25.0330, lng=121.5654)
    """
```

### 3.4 分析引擎 (`processors/analysis.py`)

核心函数签名与职责：

```python
# ── 常量定义 ──

STOP_WORDS = {"The", "This", "That", "These", "Report", "New", ...}
ORG_KEYWORDS = {"Inc", "Corp", "Ministry", "Agency", "Department", ...}
KNOWN_LOCATIONS: set[str]  # 60+ 地理实体名称（中英文）

LAYER_RISK_WEIGHTS = {
    "military": 1.0, "cyber": 0.9, "finance": 0.8, "politics": 0.8,
    "energy": 0.75, "health": 0.7, "aviation": 0.6, "agriculture": 0.6,
    "economy": 0.5, "technology": 0.5, "society": 0.4, "nature": 0.3,
}

HIGH_IMPACT_LAYERS = {"military", "cyber", "politics", "finance", "energy", "health"}

CONFIDENCE_WEIGHTS = {"L1": 4, "L2": 3, "L3": 2, "L4": 1}

# ── 分析函数 ──

def compute_timeline(items: list) -> dict:
    """按日期分组 → 每组 count + layer_counts + top10 items"""

def extract_entity_graph(items: list) -> dict:
    """
    正则提取大写命名实体 → 分类 (person/org/location) → 共现边
    Top50 实体 + 所有共现边 → {nodes, edges}
    """

def compute_corroboration(items: list) -> dict:
    """
    交叉验证矩阵 (基于事件聚类):
    1. generate_event_clusters() → 事件簇列表
    2. 构建 source → event_ids 映射
    3. Top20 来源 → 两两计算:
       shared = |events_a ∩ events_b|
       score = shared / (|events_a| + |events_b| - shared)
       confirmed = 其中 L1 事件数
       high_confidence = 其中 L1+L2 事件数
    """

def detect_anomalies(items: list) -> dict:
    """
    Z-Score 异常检测:
    1. 按 (layer, date) 聚合计数
    2. 计算每层 mean/std
    3. z = (count - mean) / max(std, 1.0)
    4. |z| > 1.5 → 标记异常 (critical/high/medium/low)
    """

def compute_risk_heatmap(items: list) -> dict:
    """
    风险热力图:
    density_norm × 0.3 + avg_conf × 0.3 + layer_risk × 0.4
    """

def analyze_gaps(items: list) -> dict:
    """
    覆盖缺口分析 (4 维度):
    - topic_gap: 图层占比 < 5% → 监测盲区
    - region_gap: 国家情报数 < 2 → 覆盖不足
    - time_gap: 连续无数据天数 > 3 → 采集异常
    - cross_source_gap: 单源占比 > 30% → 缺乏交叉验证
    """

def generate_event_clusters(items: list, scope: dict = None, limit: int = 20) -> dict:
    """
    贪心聚类算法:
    1. 按 _item_score() 降序排列
    2. 对每个 item:
       token = _claim_tokens(item)  # 中英文 2+ 字符 token 提取
       best_cluster = argmax(_cluster_match_score(item, cluster))
       if score >= 0.24 → 加入 cluster
       else → 新建 cluster
    3. 按 (item数, 来源数, 总score) 降序 → Top limit
    """

def generate_warning_indicators(
    items: list, scope: dict = None,
    requested_layers: list[str] = None,
    clusters_result: dict = None,
) -> dict:
    """
    I&W 预警框架:
    1. 事件级预警: 高敏感图层 + L1/L2 事件 → 生成预警
    2. 主题集中预警: 单图层占比 ≥ 35% → watch
    3. 单源线索预警: 高敏感单源情报过多 → 建议核查
    4. 缺失图层预警: 用户请求的图层无数据 → 采集缺口
    5. overall_level = max(所有指标 severity)
    """

def generate_situation_brief(
    items: list, scope: dict = None,
    requested_layers: list[str] = None,
) -> dict:
    """
    结构化态势简报 (130 行函数):
    1. _make_evidence() → 12 条精选证据
    2. 图层/国家聚合 → Top3 主题 + Top1 国家
    3. 生成:
       - core_findings (核心发现, 含 fact_basis + implications)
       - confirmed_facts (仅数据分布事实, 不含推断)
       - assessments (分析判断, 与事实明确分离)
       - key_judgments (含 impact 评估 + time_sensitivity + uncertainties)
       - alternative_explanations (采集偏差、来源集中、单源扩散)
       - pending_verification (缺口对应的具体核查问题)
       - contradictions (单源占比高、置信度低)
       - collection_gaps + recommended_tasks
    4. _overall_confidence() → 整体情报等级
    5. 生成 summary 文本
    """
```

### 3.5 内容合并引擎 (`merger.py`)

```python
class UnionFind:
    """不相交集合 / 并查集"""
    def add(self, x: str) -> None
    def find(self, x: str) -> str      # 路径压缩
    def union(self, a: str, b: str) -> None
    def groups(self) -> list[list[str]]

def _normalize_title(title: str) -> str:
    """去标点、小写、去空白 → 用于标题匹配"""

def _best_title(doc: BronzeDocument) -> str:
    """提取最佳标题: horizon_title > summary 首行 > text 首行"""

def _best_source_name(doc: BronzeDocument) -> str:
    """提取最佳来源名: feed_name > source_system"""

def build_merge_index(storage_root: Path) -> MergeResult:
    """
    完整合并流程:
    1. scan_bronze() → 所有文档
    2. UnionFind 分组:
       a. source_url 相同 → union
       b. content_sha256 相同 → union
       c. 归一化标题相同 → union
    3. 每个组:
       - primary_doc = 最早采集的文档
       - sources = 去重合并所有 source_system
       - source_url = 主文档的 URL
    4. 写 _merge_index.json
    """
```

## 4. API 层详细设计

### 4.1 应用生命周期

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    启动流程:
    1. 检查 bronze_storage → 空则 reseed(clear=True) 生成 Demo 数据
    2. _init_indexer() → 构建或增量更新 SQLite 索引
    3. 角色分支:
       a. API 角色:
          - run_in_executor(_prewarm_dashboard_cache) 异步预热
          - 启动 _cache_refresh_loop (每 150s 刷新)
       b. Worker 角色:
          - 启动 _reindex_loop (每 5min 增量索引)
          - 启动 OrchestratorAgent 采集+合并循环
    4. yield → 应用运行
    5. 关闭: cancel 后台 Task, stop Agent, close Indexer
    """
```

### 4.2 缓存系统

```python
# 两阶段缓存架构
_master_list_cache: dict[str, tuple[float, list]] = {}  # {key: (timestamp, items)}
_dashboard_cache: dict[str, tuple[float, object]] = {}  # {key: (timestamp, data)}
_analysis_snapshot_locks: dict[str, asyncio.Lock] = {}  # 防并发重复计算

DASHBOARD_CACHE_TTL = 300      # 5 分钟
DASHBOARD_CACHE_MAX_SIZE = 256 # LRU 驱逐上限

def _cache_set(key, value) → 写入 + 过期清理 + LRU 驱逐
def _cache_get(key) → 命中返回 / 过期返回 None
def _evict_expired_cache() → 清理两缓存中过期条目
def _prewarm_dashboard_cache() → 预热热点缓存键
```

### 4.3 IntelItem 构建流程

```python
def _build_items(
    start_date="", end_date="", layer_filter="",
    country_filter="", limit=0, use_merge_groups=True,
) -> list[IntelItem]:
    """
    完整构建流程:
    1. docs = indexer.get_all() 或 indexer.query()
    2. 加载 merge_index (若 use_merge_groups)
    3. 对每个 merged_group 或 orphan_doc:
       _make_item():
         a. 日期过滤 (start_date/end_date)
         b. extract_location_with_fallback(text, _resolve_source_name(doc), doc)
         c. _get_layer(doc):
            - 优先: doc.extensions.horizon_metadata.layer
            - 回退: classify(doc.text)
         d. _collection_confidence_from_sources(sources):
            - ≥3 独立源 → 0.85
            - 2 独立源 → 0.72
            - ≤1 独立源 → 0.55
         e. 构建 IntelItem
       - 图层/国家过滤
    4. 按 captured_at 降序排列
    """
```

## 5. Agent 系统设计

### 5.1 核心接口

```python
class Agent(ABC):
    agent_id: str
    agent_type: AgentType  # collector|processor|intelligence|analysis|system

    @abstractmethod
    async def run(self, task: AgentTaskModel) -> AgentResult: ...
    @abstractmethod
    async def validate(self, task: AgentTaskModel) -> bool: ...

class AgentCallbacks:
    on_event: Callable[[AgentEvent], Awaitable[None]]
    on_status_change: Callable[[str, AgentStatus, AgentStatus], Awaitable[None]]
    on_error: Callable[[str, str], Awaitable[None]]

class AgentRegistry:
    _agents: dict[str, type[Agent]] = {}
    @classmethod
    def register(cls, agent_cls): ...   # 自动注册
    @classmethod
    def create(cls, agent_id, **kwargs) -> Agent: ...  # 工厂方法
    @classmethod
    def list_all(cls) -> list[str]: ...  # 列出所有已注册 Agent
```

### 5.2 Agent 类型汇总

| Agent ID | 类型 | 文件 | 职责 |
|----------|------|------|------|
| `rss_collector` | collector | `agents/collectors/rss_collector.py` | RSS 源采集 |
| `social_collector` | collector | `agents/collectors/social_collectors.py` | Reddit/HN/Telegram/GitHub |
| `api_collectors` | collector | `agents/collectors/api_collectors.py` | USGS/CISA/OpenSky |
| `translator` | processor | `agents/processors/translation.py` | 多语言翻译 |
| `summarizer` | processor | `agents/processors/summarization.py` | LLM 摘要 |
| `classifier` | processor | `agents/processors/classification.py` | 图层分类 |
| `location_extractor` | processor | `agents/processors/location_extraction.py` | 地理定位 |
| `document_quality` | processor | `agents/processors/document_quality.py` | 文档呈现质量评估（不判断真值） |
| `collection_pipeline` | processor | `agents/processors/pipeline.py` | 处理流水线编排 |
| `qa_analyst` | intelligence | `agents/intelligence/qa_analyst.py` | AI 问答 |
| `report_writer` | intelligence | `agents/intelligence/report_writer.py` | 态势报告生成 |
| `super_analyst` | intelligence | `agents/intelligence/super_analyst.py` | 假设级贝叶斯+搜索分析 |
| `interpretation` | intelligence | `agents/intelligence/interpretation.py` | 分析结果解读 |
| `timeline` | analysis | `agents/analysis/timeline.py` | 时间线分析 |
| `entity_graph` | analysis | `agents/analysis/entity_graph.py` | 实体图谱 |
| `corroboration` | analysis | `agents/analysis/corroboration.py` | 交叉验证 |
| `anomaly_detector` | analysis | `agents/analysis/anomaly_detector.py` | 异常检测 |
| `risk_heatmap` | analysis | `agents/analysis/risk_heatmap.py` | 风险热力图 |
| `gap_analyzer` | analysis | `agents/analysis/gap_analyzer.py` | 缺口分析 |
| `orchestrator` | system | `agents/system/orchestrator.py` | 编排调度 |
| `indexer_agent` | system | `agents/system/indexer.py` | 索引管理 |
| `merger_agent` | system | `agents/system/merger.py` | 内容合并 |

## 6. 认证与安全

### 6.1 JWT Token 系统 (`auth/service.py`)

```python
def create_access_token(user_id: str, username: str) -> str:
    """HS256 签名，1 小时有效期，payload: {sub, username, exp, type: "access"}"""

def create_refresh_token(user_id: str) -> str:
    """HS256 签名，7 天有效期，payload: {sub, exp, type: "refresh"}"""

def decode_token(token: str) -> dict | None:
    """验证签名 + 过期检查 → 返回 payload 或 None"""

def refresh_access_token(refresh_token: str) -> dict:
    """验证 refresh_token → 签发新 access_token + 新 refresh_token"""
```

### 6.2 中间件安全

```python
# Body Size Limit: 拒绝 > 2MB 的请求 (返回 413)
_MAX_BODY_BYTES = 2 * 1024 * 1024

# 限流: 滑动窗口
_RATE_LIMIT_WINDOW = 60       # 窗口秒数
_RATE_LIMIT_MAX = 300         # GET 上限/窗口
_RATE_LIMIT_WRITE_MAX = 60    # POST 上限/窗口

# Auth 中间件: Cookie(osint_access_token) 或 Bearer Header
# Refresh Token 自动续期: osint_refresh_token → 签发新 token 对
```

## 7. 前端组件详细设计

### 7.1 组件树

```
App (根组件)
├── ErrorBoundary (React 错误边界)
├── StatusDot (WebSocket 连接状态指示灯)
├── MapView (MapLibre GL 地图, 天地图瓦片)
│   └── IntelCard popups (点击标记弹出)
├── LayerPanel (12 图层筛选面板, SVG 图标+颜色)
├── MessageFeed (情报信息流, 虚拟滚动)
│   └── IntelCard (可展开详情 + 来源溯源)
├── MobileMenu (移动端 < 767px)
├── AskPanel / ReportPanel
├── StatsPanel (趋势图 + 来源矩阵 + 地理分布)
├── IntelAnalysisPanel (Tab 切换 7 种分析视图)
│   ├── TimelineView (时间线)
│   ├── EntityGraphView (实体关系图)
│   ├── CorroborationView (交叉验证矩阵)
│   ├── AnomalyView (异常事件)
│   ├── RiskHeatmapView (风险热力图)
│   └── GapAnalysisView (覆盖缺口)
├── SuperAnalysisPanel + Sidebar
├── LoginPage / RegisterPage
└── AdminPanel
```

### 7.2 数据轮询

```typescript
// hooks/useDashboardData.ts
function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null);
  useEffect(() => {
    const poll = setInterval(async () => {
      const result = await api.getDashboard({ page: 1, page_size: 100 });
      setData(result);
    }, 10000); // 10s 间隔
    return () => clearInterval(poll);
  }, []);
  return data;
}
```

### 7.3 响应式设计

```typescript
// 断点: 767px
function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(window.innerWidth < 767);
  // ... resize listener
  return mobile;
}

// 移动端布局差异:
// - 地图全屏 + 底部抽屉式信息流 (替代分屏)
// - 图层选择器: 水平可滚动条 (替代垂直列表)
// - 分析面板: 全屏 Overlay (替代侧边栏)
```

### 7.4 图层元数据

```typescript
// types.ts
type IntelLayer =
  | 'nature' | 'economy' | 'finance' | 'politics'
  | 'military' | 'aviation' | 'technology' | 'society'
  | 'energy' | 'agriculture' | 'health' | 'cyber';

const LAYER_META: Record<IntelLayer, { label: string; color: string }> = {
  nature:      { label: '自然生态', color: '#2ecc71' },
  economy:     { label: '经济产业', color: '#3498db' },
  finance:     { label: '金融',     color: '#f39c12' },
  politics:    { label: '政治外交', color: '#9b59b6' },
  military:    { label: '军事',     color: '#e74c3c' },
  aviation:    { label: '民航交通', color: '#607d8b' },
  technology:  { label: '科技',     color: '#ff4081' },
  society:     { label: '社会民生', color: '#e91e63' },
  energy:      { label: '能源资源', color: '#ff5722' },
  agriculture: { label: '农业食品', color: '#4caf50' },
  health:      { label: '公共卫生', color: '#00bcd4' },
  cyber:       { label: '网络空间', color: '#1a237e' },
};
```

## 8. 部署配置

### 8.1 核心环境变量

```bash
# LLM
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 角色
OSINT_ROLE=api              # api | worker | all

# 性能
ANALYSIS_REALTIME_ITEM_LIMIT=3000
STATS_DEFAULT_DAYS=14

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# OpenCode (可选, 生产环境按需开启)
OPENCODE_SUPER_ANALYSIS_ENABLED=true
OPENCODE_REPORT_ENABLED=false
OPENCODE_INTERPRET_ENABLED=false

# 网络代理
PROXY_URL=http://127.0.0.1:7890
```

### 8.2 Systemd 服务

```ini
[Unit]
Description=OSINT Network Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/osint-network
EnvironmentFile=/opt/osint-network/.env
ExecStart=/opt/osint-network/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 8.3 Nginx 反向代理

```nginx
server {
    listen 80;
    root /opt/osint-network/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 8.4 部署命令

```bash
# 后端同步 + 重启
rsync -avz -e "ssh -p 9022" backend/ \
  ubuntu@221.239.50.138:/opt/osint-network/backend/
ssh osint-server 'sudo systemctl restart osint-network.service'

# 前端构建 + 同步
cd frontend && npm run build
rsync -avz -e "ssh -p 9022" frontend/dist/ \
  ubuntu@221.239.50.138:/opt/osint-network/frontend/dist/
```

## 9. 添加新情报图层的步骤

按顺序修改 10 个文件:

| 步骤 | 文件 | 修改内容 |
|------|------|---------|
| 1 | `backend/models.py:10` | `IntelLayer` 枚举 + 新值 |
| 2 | `backend/processors/llm_classifier.py` | SYSTEM_PROMPT 添加新层定义 + 消歧规则 |
| 3 | `backend/processors/classifier.py` | `_LAYER_RULES` 添加关键词组 |
| 4 | `frontend/src/types.ts` | `IntelLayer` 类型 + `LAYER_META` (label + color) |
| 5 | `frontend/src/icons/<NewIcon>.tsx` | 创建 SVG 图标组件 |
| 6 | `frontend/src/components/LayerPanel.tsx` | 注册到 `iconMap` |
| 7 | `frontend/src/App.tsx`, `AskPanel.tsx`, `ReportPanel.tsx` | 添加到 `ALL_LAYERS` |
| 8 | `frontend/src/components/analysis/TimelineView.tsx` | 添加到 `LAYERS` |
| 9 | `backend/osint_sources.py` | 添加数据源 + `layer_bias` |
| 10 | `backend/collectors/horizon_bridge.py` | 添加 RSS feeds 到 `_DEFAULT_RSS_FEEDS` |
