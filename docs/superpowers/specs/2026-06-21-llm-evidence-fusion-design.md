# LLM 证据融合接入结构化打分链路 — 设计

## 背景

世界球花的 OSINT pipeline 接了多个数据源：懂球帝（结构化文本）、中英文搜索（DDG/Sogou）、RSS（BBC/ESPN/SkySports/RSSHub/虎扑/微博/懂球帝早报）、Open-Meteo 天气、用户手填笔记。

但驱动 VerdictCard（方向 / 置信度 / 概率条）的 `factor_registry.py` 只读懂球帝的 `fundamental.*` 文本，靠几条写死的正则（`_FORM_RE`/`_H2H_RE`/`_SIDELINE_RE`/`_STANDINGS_RE`）抽取"近期战绩/历史交锋/伤停/积分排名"。搜索、RSS、用户笔记里的同类信息因为格式不匹配正则，从未真正影响打分——只在报告里摆着。

天气因子同样浪费：Open-Meteo 抓回了真实降水概率/风速/温度，但 `weather.exposure` 只要 `has_weather` 就给固定 `+0.03`，不读数值。

本设计解决：让 LLM 把多源证据里同类信息抽取成结构化字段，喂给现有打分公式；同时把天气因子改成按数值打分。

## 范围

- **In scope**：新增 LLM 抽取层，替换"从文本找数字"这一步；天气因子按数值打分；LLM 失败时正则兜底。
- **Out of scope**（明确不做，避免范围蔓延）：
  - 不改打分公式本身的算术逻辑（`_score_recent_form` 等系数、上下限不变）。
  - 不改 `confidence.py` 的置信度分级逻辑。
  - 不接入 SofaScore/FBref/Transfermarkt（这是"数据源数量"问题，不是"现有数据没用好"问题，留作后续）。
  - 不改 `match_report.py`/`llm_qa.py` 的自由文本问答链路（它们已经能读全部证据，本次不动）。
  - 不引入数据库/向量库做证据存储，沿用现有内存 `evidence: list[OsintEvidence]`。

## 架构

```
pipeline.py: _collect_zero_config_sources()
        │  (evidence 收集完毕，topic 包含 fundamental.* / search.* / news.rss.* / user.note)
        ▼
factor_registry.build_factors(request, profile, evidence)
        │
        ├─ evidence_extraction.extract(evidence, request)  ← 新增
        │     │
        │     ├─ 有 LLM_API_KEY 且调用成功 → 返回 ExtractedFacts（结构化字段）
        │     └─ 无 key / 调用失败 / 超时 / JSON 解析失败 → 返回 None
        │
        ├─ if ExtractedFacts is not None:
        │     用其字段喂给 _score_recent_form / _score_h2h / _score_squad / _score_standings
        │   else:
        │     沿用现有正则路径（_FORM_RE 等不删除，作为兜底）
        │
        └─ weather 因子：改读 open_meteo 抓回的 precip/wind/temp 数值打分（规则，非 LLM）
```

`evidence_extraction.py` 是新文件，单一职责：把 `list[OsintEvidence]` 变成一个结构化 dataclass，不关心打分公式，也不关心调用方是谁。`factor_registry.py` 是唯一调用方。

## 数据结构

```python
@dataclass
class ExtractedFacts:
    home_form: tuple[int, int, int] | None   # (wins, draws, losses)
    away_form: tuple[int, int, int] | None
    h2h_home_wins: int | None
    h2h_draws: int | None
    h2h_home_losses: int | None
    home_absences: int | None
    away_absences: int | None
    home_rank: int | None
    away_rank: int | None
```

字段语义与现有正则抽取结果一一对应，这样 `_score_*` 函数的算术逻辑保持不变，只是输入源从"正则 match 文本"换成"结构化字段直接读"。

## LLM 调用

- 复用 `name_translation.py` 的同步 httpx 调用约定（项目里 sync pipeline 跑在 `asyncio.to_thread` 里，不用 async client）。
- `response_format: {"type": "json_object"}`，`temperature: 0`（抽取任务要确定性，不要创造性）。
- 输入：拼接 `evidence` 中 topic 属于 `fundamental.*` / `search.*` / `news.rss.*` / `user.note` 的 `raw_excerpt`（每条标注来源），系统提示词要求"只抽取证据中明确出现的数字，没有就填 null，不得编造"。
- 超时：复用 `match_report.py` 的 `_TIMEOUT = 45.0` 量级。
- 失败处理：网络异常、HTTP 错误、JSON 解析失败、字段类型不对 → 统一 `except Exception` 兜底返回 `None`，并 `log.warning`，不抛到调用方。

## 调用频率与缓存

`run_prediction_sync` 本身在 job 级别被 `warm_cache`/请求哈希复用（同一场比赛同一请求不会重复跑整条 pipeline），所以 `evidence_extraction.extract()` 天然只在 job 首次构建时调用一次，不需要额外加缓存层。

## 天气因子规则化打分

`open_meteo.py` 的 `claim` 字符串里已经有降水概率/风速/温度。`weather.exposure` 改为：
- 解析 `raw_excerpt`（JSON，已是 Open-Meteo 原始响应）里的 `precipitation_probability_max` / `wind_speed_10m_max`。
- 规则示例（具体阈值在实现阶段定，不在这里锁死）：降水概率高或风速高 → 轻微方向中性的"比赛质量下降"信号（保持 `direction="neutral"`，但 `confidence`/`impact` 幅度随数值变化，而不是写死 0.03）。
- 这是规则代码，不走 LLM。

## 测试策略

- `evidence_extraction.py`：mock httpx 返回固定 JSON，断言字段解析正确；mock 异常/超时，断言返回 `None`。
- `factor_registry.py`：
  - 现有测试（基于正则路径）保持不变，新增一条路径覆盖"`evidence_extraction.extract` 返回 mock 的 `ExtractedFacts`"场景，断言打分结果和直接构造同等正则文本时一致（验证两条路径的算术逻辑等价）。
  - 新增"LLM 抽取失败 → 正则兜底"的回归测试。
  - 新增天气因子按数值打分的测试（不同 precip/wind 组合对应不同 impact）。

## 不确定性与待实现阶段决定的细节

- 天气打分的具体阈值/系数（留给实现阶段调参，不影响架构）。
- LLM 抽取 prompt 的具体措辞（留给实现阶段，需要测试集验证不编造数字）。
