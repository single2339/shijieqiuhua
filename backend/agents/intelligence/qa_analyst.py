"""Q&A intelligence agent — answers questions based on existing intelligence data."""

from __future__ import annotations

import hashlib
from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.models import IntelLayer
from backend.processors.classifier import classify

_SYSTEM_QA = (
    "你是一名专业的情报分析师。基于提供的上下文情报数据，用简体中文回答用户的问题。"
    "引用具体的情报来源和时间，保持客观、准确。如果数据不足以回答，请明确指出。"
    "不编造信息，不添加外部知识。"
)


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


@AgentRegistry.register
class QAAgent(BaseAgent):
    agent_id = "qa_analyst"
    agent_type = AgentType.INTELLIGENCE

    def __init__(self, indexer=None, callbacks=None):
        super().__init__(callbacks)
        self._indexer = indexer

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        question = task.params.get("question", "")
        layer_filter = task.params.get("layer")
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        max_items = task.params.get("max_items", 30)

        indexer = self._indexer
        if indexer is None:
            return {"answer": "索引器未初始化，无法检索情报数据。", "references": []}

        docs = indexer.get_all()
        seen: set[str] = set()
        relevant: list[dict] = []

        for doc in docs:
            text = doc.text
            if not text:
                continue
            body_hash = hashlib.md5(text.encode()).hexdigest()
            if body_hash in seen:
                continue
            seen.add(body_hash)

            ext = doc.extensions or {}
            title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]
            layer = _get_layer(doc)
            if layer_filter and layer.value != layer_filter:
                continue

            captured = doc.captured_at[:10] if doc.captured_at else ""
            if start_date and captured < start_date:
                continue
            if end_date and captured > end_date:
                continue

            relevant.append({
                "title": title.split("\n")[0],
                "content": text[:500],
                "source": doc.source_system,
                "date": captured,
                "layer": layer.value,
            })

            if len(relevant) >= max_items:
                break

        if not relevant:
            return {"answer": "系统暂无相关情报数据可供分析。", "references": []}

        context_lines = []
        for i, r in enumerate(relevant, 1):
            context_lines.append(
                f"[{i}] {r['date']} | {r['source']} | {r['layer']}\n"
                f"    标题: {r['title']}\n"
                f"    内容: {r['content'][:300]}\n"
            )
        context = "\n".join(context_lines)
        user_prompt = f"## 情报数据\n\n{context}\n\n## 问题\n\n{question}"

        answer = await self._call_llm(_SYSTEM_QA, user_prompt)
        refs = [{"title": r["title"], "source": r["source"], "date": r["date"]} for r in relevant[:10]]

        return {
            "answer": answer or "AI分析暂时不可用（API密钥未配置或请求失败）。",
            "references": refs,
        }
