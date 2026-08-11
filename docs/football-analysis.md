# Football Analysis Branch

This branch adds a football-specific analysis vertical inspired by
`a872034547-cpu/Football-2026`.

## What We Learned

Football-2026 is a Chrome MV3 extension focused on Titan007 match pages. Its
useful product pattern is:

- collect fixture, team form, 1x2 odds, Asian handicap, over/under, corners, and
  same-handicap history;
- normalize market odds into implied probabilities;
- run a deterministic local model before asking an LLM;
- attach web intelligence such as injuries, weather, team news, and lineup
  signals;
- report value, uncertainty, and risk instead of only a direction.

The extension also includes browser DOM extraction and public-sync code. Those
parts are not copied into OSINT Network. The OSINT branch keeps the football
logic server-side and source-agnostic so collectors can be added later.

## First Scope

`backend.football` provides a deterministic match analyzer:

- de-margin 1x2 market probabilities;
- estimate home/away scoring rates from recent goals for/against;
- run a Poisson score matrix for win/draw/loss, top scores, and over 2.5;
- compare model probability with market odds for positive expected value;
- cap Kelly stake suggestions at a small research limit;
- flag large odds movement, external risk signals, and thin intelligence.

API entrypoint:

```http
POST /api/football/analyze
```

This is research and risk analysis only. It does not provide guaranteed picks or
betting advice.

## 体彩官方盘口参考

当中国体育彩票覆盖比赛时，系统从 `sporttery.cn` 取得官方胜平负（HAD）及可用的让球胜平负（HHAD）快照。赔率只作为可追溯的官方市场参考，不显示投注、收益或购买建议，也不能单独产生方向结论：没有达到最低基本面证据覆盖时，即使有盘口，结论仍为“信息不足”。

十进制赔率先去除赔率边际，逐项按下式归一化：

```text
p_i = (1 / o_i) / Σ(1 / o_j)
```

其中 `o_i` 是主胜、平局或客胜的十进制赔率，三个归一化概率的和为 1。满足基本面证据要求时，比分矩阵模型与官方胜平负概率融合：有两项或更多基本面信号时采用模型 65% / 官方市场 35%；只有一项基本面信号时采用模型 45% / 官方市场 55%。同一权重也用于完整 HHAD 行的让球结果。

让球数始终以主队视角表达：`+1` 表示主队受让一球，`-1` 表示主队让一球。赛后结算只使用官方 90 分钟常规时间比分；加时赛和点球大战不计入普通胜平负或让球胜平负结算。

## 概率呈现

完成且证据充分的研判会按概率从高到低显示主胜、平局、客胜三个精确点概率。展示百分比经过取整修正后合计为 100%，不是固定的“±4%”区间。首选结果仅在其概率比第二名至少高 5 个百分点时标记为“清晰”；低于该阈值会明确提示“优势不足，存在接近结果”。

为让手机端优先看到结论，研判结论和概率始终直接显示；完整分析过程、证据与因子视图默认折叠，用户可按需展开。

## Later Collectors

Good next additions are:

- football news and injury collectors;
- fixture and odds adapters behind provider-neutral schemas;
- a football dashboard tab for match watchlists and risk-ranked value edges;
- provenance tracking for each odds/intelligence signal.
