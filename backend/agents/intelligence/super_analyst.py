"""Super Analysis agent — Bayesian + web search + LLM structured intelligence analysis.

Uses skills: osint-core, osint-verify, osint-analysis, super-analysis, bayesian-reasoning
"""

from __future__ import annotations

import asyncio
import hashlib
import os

from pathlib import Path
from typing import Any

import httpx
import jieba

from backend.agents.base import AgentType, BaseAgent
from backend.agents.intelligence._bayesian import (
    SOURCE_PRIORS,
    compute_bayesian,
    source_prior_class,
)
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.agents.skill import SkillLoader
from backend.bronze_reader import scan_bronze
from backend.llm_config import get_llm_client
from backend.models import IntelLayer, Verdict
from backend.processors.classifier import classify
from backend.processors.embedding_index import EmbeddingIndex
from backend.processors.progress import set_progress

# Base system prompt — OSINT core principles are embedded directly so the
# LLM follows them even before skill augmentations are appended.
_SYSTEM_SUPER_ANALYSIS_BASE = (
    "你是超级分析师，严格遵循开源情报（OSINT）方法论进行深度分析。\n\n"
    "## 核心原则（必须遵守）\n"
    "1. **三方验证** — 任何结论至少3个独立来源交叉确认，禁止基于单一来源做出确定结论\n"
    "2. **区分事实与推测** — 明确标注哪些是已确认事实，哪些是基于部分证据的推测\n"
    "3. **逆向思维** — 追问“谁会从中受益”、“谁想掩盖什么”，主动寻找反驳假设的证据\n"
    "4. **链上留痕** — 每个结论可回溯至原始来源，不编造信息\n"
    "5. **置信度评级** — 所有发现必须标注 L1-L4 置信度：\n"
    "   L1-确认（≥3独立来源交叉验证）、L2-高可信（2个独立来源支持）\n"
    "   L3-中可信（1个可靠来源）、L4-推测（基于间接证据的合理推断）\n\n"
    "## 分析流程（严格4步）\n"
    "第1步 情报整理 → 第2步 关联匹配 → 第3步 贝叶斯分析 → 第4步 结论生成\n"
    "禁止跳过任何步骤，禁止在未完成前3步的情况下给出结论。"
)

BING_API_KEY = os.getenv("BING_API_KEY", "")


def _tokenize(text: str) -> set[str]:
    """Tokenize Chinese text using jieba cut_for_search for better recall.

    cut_for_search breaks compounds into smaller units (e.g. '台海局势'
    becomes ['台海', '局势', '台', '海']), improving overlap with queries.
    """
    tokens = set()
    for w in jieba.cut_for_search(text):
        w = w.strip()
        if not w:
            continue
        # Keep CJK characters, filter pure punctuation/whitespace
        has_cjk = any('一' <= c <= '鿿' or '㐀' <= c <= '䶿' for c in w)
        if has_cjk or len(w) >= 2:
            tokens.add(w)
    return tokens


def _relevance_score(question: str, text: str) -> float:
    """Compute semantic relevance via jieba token overlap on full document."""
    q_tokens = _tokenize(question)
    if not q_tokens:
        return 0.0
    # Sample up to 3000 chars to capture document gist
    doc_tokens = _tokenize(text[:3000])
    if not doc_tokens:
        return 0.0
    overlap = q_tokens & doc_tokens
    # Fraction of question tokens matched in this document
    recall = len(overlap) / len(q_tokens)
    return recall


def _bayesian_to_l1l4(posterior: float, prior_class: str, evidence_items: list) -> str:
    """Map posterior probability + source credibility + evidence quality to OSINT L1-L4.

    L1 确认: ≥3 high-quality evidence, posterior ≥ 0.85, high-credibility source
    L2 高可信: ≥2 evidence items, posterior ≥ 0.7
    L3 中可信: ≥1 evidence item, posterior ≥ 0.5
    L4 推测: posterior < 0.5 or only indirect/low-quality evidence
    """
    high_quality = sum(
        1 for e in evidence_items
        if e.get("quality", "D") in ("A", "B")
    )
    total_evidence = len(evidence_items)

    if posterior >= 0.85 and total_evidence >= 3 and high_quality >= 2 and prior_class in ("high", "medium"):
        return "L1-确认"
    elif posterior >= 0.7 and total_evidence >= 2 and high_quality >= 1:
        return "L2-高可信"
    elif posterior >= 0.5 and total_evidence >= 1:
        return "L3-中可信"
    else:
        return "L4-推测"


def _cross_match_relation(overlap_score: int) -> str:
    """Classify cross-match relationship based on token overlap strength.

    佐证 (corroboration): ≥ 8 overlapping tokens — web source strongly supports intel item
    补充 (supplementary): 3-7 overlapping tokens — web source adds context
    弱关联 (weak): < 3 — minimal overlap, may be unrelated
    """
    if overlap_score >= 8:
        return "佐证"
    elif overlap_score >= 3:
        return "补充"
    else:
        return "弱关联"


def _get_layer(doc) -> IntelLayer:
    ext = getattr(doc, "extensions", {}) or {}
    if isinstance(ext, dict):
        meta = ext.get("horizon_metadata", {})
        if isinstance(meta, dict) and meta.get("layer"):
            try:
                return IntelLayer(meta["layer"])
            except ValueError:
                pass
    return classify(doc.text)


async def _search_bing(query: str, topn: int = 8) -> list[dict]:
    """Search Bing China for web results."""
    if not BING_API_KEY:
        return []
    results: list[dict] = []
    try:
        async with get_llm_client() as client:
            r = await client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": query, "count": topn, "mkt": "zh-CN"},
                headers={"Ocp-Apim-Subscription-Key": BING_API_KEY},
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("webPages", {}).get("value", []):
                    title = item.get("name", "")
                    snippet = item.get("snippet", "")
                    url = item.get("url", "")
                    results.append({
                        "title": title,
                        "snippet": snippet[:300],
                        "url": url,
                    })
    except Exception:
        pass
    return results


async def _search_ddg(query: str, topn: int = 10) -> list[dict]:
    """Search via DuckDuckGo — free, no API key, works globally."""
    try:
        from ddgs import DDGS
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=topn)),
        )
        results: list[dict] = []
        for r in raw:
            results.append({
                "title": r.get("title", ""),
                "snippet": (r.get("body", "") or "")[:300],
                "url": r.get("href", ""),
            })
        return results
    except Exception:
        return []


async def _web_search(query: str) -> list[dict]:
    """Search the web for supplementary context. Returns up to 15 deduped results.

    Uses DuckDuckGo (free, no key) as primary; Bing API as optional fallback.
    """
    # Primary: DuckDuckGo (no API key needed, works globally)
    ddg_task = _search_ddg(query, topn=10)

    # Fallback: Bing (only if API key is configured)
    bing_task = _search_bing(query, topn=8) if BING_API_KEY else None

    tasks = [ddg_task]
    if bing_task is not None:
        tasks.append(bing_task)
    all_results = await asyncio.gather(*tasks)

    seen: set[str] = set()
    merged: list[dict] = []
    for results in all_results:
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                merged.append(r)
    return merged[:15]


@AgentRegistry.register
class SuperAnalysisAgent(BaseAgent):
    agent_id = "super_analyst"
    agent_type = AgentType.INTELLIGENCE

    # Default skills this agent should always load
    DEFAULT_SKILLS = [
        "osint-core",
        "osint-verify",
        "osint-analysis",
        "super-analysis",
        "bayesian-reasoning",
    ]

    def __init__(self, storage_root: str | Path = "bronze_storage", callbacks=None):
        super().__init__(callbacks)
        self._storage = Path(storage_root)

        # Auto-load default skills
        self._load_default_skills()

    def _load_default_skills(self):
        """Load the default skill set for this agent."""
        for skill_name in self.DEFAULT_SKILLS:
            try:
                self.load_skill(skill_name)
            except FileNotFoundError:
                pass  # Skip if skill not available

    async def _call_llm_with_skills(self, user_content: str, temperature: float | None = None) -> str | None:
        """Call LLM with the full skill-augmented system prompt."""
        # Build system prompt by combining base + skill augmentations
        system_prompt = self._build_system_prompt(_SYSTEM_SUPER_ANALYSIS_BASE)

        # Use the base _call_llm but with our combined system prompt
        temp = temperature if temperature is not None else self._skill_param("temperature", self.temperature)
        max_tok = self._skill_param("max_tokens", self.max_tokens)

        payload = {
            "model": self.model,
            "max_tokens": max_tok,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temp,
        }

        try:
            async with get_llm_client() as client:
                r = await client.post(f"{os.getenv('LLM_BASE_URL', 'https://api.deepseek.com/v1')}/chat/completions", json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return None

    def _build_system_prompt(self, base: str) -> str:
        """Combine base prompt with all loaded skill augmentations."""
        parts = [base]
        for skill in self._loaded_skills:
            aug = skill.render_prompt_augment()
            if aug:
                parts.append(aug)
        return "\n\n".join(parts)

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        question = task.params.get("question", "")
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        enable_web_search = task.params.get("web_search", True)

        # Load any additional skills specified in the task
        if task.skills:
            for skill_name in task.skills:
                try:
                    self.load_skill(skill_name)
                except FileNotFoundError:
                    pass

        docs = scan_bronze(self._storage)
        total_docs = len(docs)
        set_progress("collecting", f"第1步·情报整理：数据库中检索到 {total_docs} 条情报，开始语义检索...", percent=5,
                     total_docs=total_docs)
        hash_to_doc: dict[str, tuple] = {}
        for doc in docs:
            text = doc.text
            if not text:
                continue
            body_hash = hashlib.md5(text.encode()).hexdigest()
            captured = doc.captured_at[:10] if doc.captured_at else ""
            if start_date and captured < start_date:
                continue
            if end_date and captured > end_date:
                continue
            if body_hash not in hash_to_doc:
                hash_to_doc[body_hash] = (doc, captured)

        # Try embedding-based semantic pre-filter
        index = EmbeddingIndex(self._storage, index_dir="embedding_index")
        index.load()
        embedding_hits: dict[str, float] = {}

        if index.is_loaded:
            set_progress("collecting", f"第1步·语义向量检索中... (索引 {index.size} 篇)", percent=8,
                         total_docs=index.size)
            hits = index.search(question, top_k=100)
            embedding_hits = {h: s for h, s in hits}

        use_embeddings = len(embedding_hits) > 0
        candidate_hashes = set(embedding_hits.keys()) if use_embeddings else set(hash_to_doc.keys())
        total_candidates = len(candidate_hashes)

        # Web search starts concurrently with evidence scoring so the total
        # wait is dominated by the slower of the two, not their sum.
        web_task = asyncio.create_task(_web_search(question)) if enable_web_search else None

        if use_embeddings:
            set_progress("collecting", f"情报整理·证据评分：语义检索命中 {total_candidates} 篇，逐条计算后验概率...", percent=10,
                         total_docs=total_docs, relevant_count=total_candidates)

        scored: list[tuple[float, dict]] = []
        for i, body_hash in enumerate(candidate_hashes):
            if i % 100 == 0 and i > 0 and use_embeddings:
                set_progress("collecting", f"情报整理·证据评分中... ({i}/{total_candidates})",
                             percent=10 + int(15 * i / total_candidates),
                             total_docs=total_candidates, processed=i)
            if i % 500 == 0 and i > 0 and not use_embeddings:
                set_progress("collecting", f"情报整理·证据评分中... ({i}/{total_candidates})",
                             percent=5 + int(20 * i / total_candidates),
                             total_docs=total_candidates, processed=i)

            entry = hash_to_doc.get(body_hash)
            if entry is None:
                continue
            doc, captured = entry
            text = doc.text

            ext = doc.extensions or {}
            title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]
            layer = _get_layer(doc)

            posterior, trace, verdict, method, prior_quality, prior_class, evidence_items = compute_bayesian(
                text, doc.source_system
            )

            if use_embeddings:
                similarity = embedding_hits.get(body_hash, 0.0)
                combined = similarity * 100 + posterior * 10
            else:
                relevance = _relevance_score(question, text)
                combined = relevance * 100 + posterior * 10

            l1l4 = _bayesian_to_l1l4(posterior, prior_class, evidence_items)

            scored.append((combined, {
                "title": title.split("\n")[0],
                "source": doc.source_system,
                "date": captured,
                "layer": layer.value,
                "confidence": round(posterior, 3),
                "confidence_l1l4": l1l4,
                "verdict": verdict.value if hasattr(verdict, "value") else str(verdict),
                "prior_class": prior_class,
                "prior_probability": SOURCE_PRIORS.get(prior_class, SOURCE_PRIORS["unknown"])["probability"],
                "evidence_items": [
                    {"name": e["name"], "quality": e["quality"], "lr": e["lr"], "direction": e["direction"]}
                    for e in evidence_items
                ],
                "bayesian_trace": [round(t, 4) for t in trace],
                "content_snippet": text[:200],
            }))

        scored.sort(key=lambda x: -x[0])
        top_items = [item for _, item in scored[:20]]

        set_progress("collecting", f"情报整理·网络搜索：等待外部数据返回...", percent=28,
                     relevant_count=len(top_items))

        if web_task is not None:
            web_results = await web_task
        else:
            web_results = []

        set_progress("crossmatching", f"第2步·关联匹配：交叉匹配 {len(top_items)} 条情报与 {len(web_results)} 条网络数据...", percent=32,
                     internal_count=len(top_items), web_count=len(web_results))

        # Brief yield so the frontend poll can catch the crossmatching phase
        # before we jump to analyzing (cross-match is near-instant).
        await asyncio.sleep(0.6)

        if not top_items and not web_results:
            return {
                "question": question,
                "analysis": "系统暂无相关情报数据可供分析。",
                "relevant_items": [],
                "web_results": [],
            }

        used_web: set[int] = set()
        item_web_map: dict[int, list[tuple[int, int]]] = {i: [] for i in range(len(top_items))}

        if web_results and top_items:
            for wi, wr in enumerate(web_results):
                web_text = (wr.get("title", "") + " " + wr.get("snippet", "")).lower()
                web_tokens = set(web_text.split())
                if not web_tokens:
                    continue
                best_score = 0
                best_item = -1
                for ii, item in enumerate(top_items):
                    item_text = (item["title"] + " " + item["content_snippet"]).lower()
                    item_tokens = set(item_text.split())
                    overlap = len(web_tokens & item_tokens)
                    if overlap > best_score:
                        best_score = overlap
                        best_item = ii
                if best_score >= 3 and best_item >= 0:
                    item_web_map[best_item].append((wi, best_score))
                    used_web.add(wi)

        # Build the context for the LLM
        context_parts = []

        if top_items:
            context_parts.append(f"## 内部情报（{len(top_items)}条）\n")
            for i, item in enumerate(top_items):
                evidence_str = ", ".join(
                    f"{e['name']}(LR={e['lr']}, {e['direction']})"
                    for e in item["evidence_items"]
                )
                context_parts.append(
                    f"[{i+1}] {item['date']} | {item['source']} | {item['layer']}\n"
                    f"标题: {item['title']}\n"
                    f"置信度: {item['confidence_l1l4']} | 后验概率: {item['confidence']}\n"
                    f"摘要: {item['content_snippet']}\n"
                    f"贝叶斯评估: 先验={item['prior_class']}({item['prior_probability']}), "
                    f"后验={item['confidence']}, 判断={item['verdict']}\n"
                    f"证据: {evidence_str}\n"
                )

        if web_results:
            context_parts.append(f"\n## 网络数据（{len(web_results)}条）\n")
            for i, wr in enumerate(web_results):
                context_parts.append(
                    f"[W{i+1}] {wr['title']}\n"
                    f"摘要: {wr['snippet']}\n"
                    f"URL: {wr['url']}\n"
                )

        if web_results and top_items:
            context_parts.append("\n## 交叉匹配\n")
            for item_idx, web_entries in item_web_map.items():
                if web_entries:
                    parts = []
                    for wi, score in web_entries:
                        relation = _cross_match_relation(score)
                        parts.append(f"W{wi+1}({relation})")
                    context_parts.append(f"内部情报[{item_idx+1}] ←→ 网络数据: {', '.join(parts)}")

        context = "\n".join(context_parts)
        user_prompt = (
            f"## 用户问题\n\n{question}\n\n"
            f"## 可用情报\n\n{context}\n\n"
            f"请严格按照以下4步框架进行综合分析（禁止跳过任何步骤）：\n\n"
            f"**第1步：情报整理**\n"
            f"- 从上方的“内部情报”和“网络数据”中提取与问题相关的所有信息\n"
            f"- 对每条信息标注来源可信度等级和 L1-L4 置信度\n"
            f"- 区分“已确认事实”和“待验证推测”\n\n"
            f"**第2步：关联匹配**\n"
            f"- 参照“交叉匹配”中的关系标注（佐证/补充/弱关联）\n"
            f"- 识别内部情报与网络数据之间的一致性、互补性和矛盾点\n"
            f"- 标注未匹配的独立信息，评估其可信度\n\n"
            f"**第3步：贝叶斯分析**\n"
            f"- 基于问题设定初始假设的先验概率\n"
            f"- 逐条应用证据计算似然比，更新后验概率\n"
            f"- 给出最终后验概率和判断（已验证/不确定/已证伪）\n\n"
            f"**第4步：结论生成**\n"
            f"- 核心发现（标注 L1-L4 置信度）\n"
            f"- 至少提供 2 个替代解释\n"
            f"- 列出待确认项和下一步建议"
        )

        set_progress("analyzing", "第4步·结论生成：调用 AI 模型进行深度推理分析...（通常需要 1-3 分钟）", percent=35)

        analysis = await self._call_llm_with_skills(user_prompt, temperature=0.3)

        return {
            "question": question,
            "analysis": analysis or "AI分析暂时不可用。",
            "relevant_items": top_items,
            "web_results": web_results,
        }
