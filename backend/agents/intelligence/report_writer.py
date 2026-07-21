"""Report intelligence agent — generates structured Chinese situation briefs."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.models import IntelLayer
from backend.processors.classifier import classify
from backend.processors.location import extract_location

_SYSTEM_REPORT = (
    "你是一名专业的情报分析官。根据提供的上下文情报数据，生成一份结构化中文态势简报。"
    "简报格式要求：\n"
    "1. 先给出整体态势总结（150字以内）\n"
    "2. 按主题分节，每节以「## 标题」开头\n"
    "3. 每节包含3-5条关键发现，每条控制在80字以内\n"
    "4. 对关键数据点标注情报来源和日期\n"
    "5. 最后附置信度评估\n\n"
    "只使用提供的情报数据，不编造信息。"
)


def _build_template_report(topic_desc: str, relevant: list[dict], source_count: int) -> dict[str, Any]:
    sections = []
    by_layer: dict[str, list[dict]] = {}
    for item in relevant:
        by_layer.setdefault(item["layer"], []).append(item)
    for layer_name, items in by_layer.items():
        lines = []
        for item in items[:10]:
            source = item.get("source", "未知来源")
            date = item.get("date", "")
            title = item.get("title", "")
            lines.append(f"- {title}（{source}，{date}）")
        sections.append({
            "heading": f"## {layer_name} 层面",
            "body": "\n".join(lines),
        })
    return {
        "title": f"态势简报：{topic_desc}",
        "summary": f"共{len(relevant)}条情报，来自{source_count}个来源。以下为确定性模板汇总，未使用 LLM 生成。",
        "sections": sections,
        "item_count": len(relevant),
        "source_count": source_count,
    }


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
class ReportAgent(BaseAgent):
    agent_id = "report_writer"
    agent_type = AgentType.INTELLIGENCE

    def __init__(self, indexer=None, callbacks=None):
        super().__init__(callbacks)
        self._indexer = indexer

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        topic = task.params.get("topic", "")
        country = task.params.get("country", "")
        layer_filter = task.params.get("layer")
        days = task.params.get("days", 7)
        max_items = task.params.get("max_items", 50)
        selected_materials = task.params.get("source_materials") or []

        indexer = self._indexer
        if indexer is None and not selected_materials:
            return {
                "title": "态势简报",
                "summary": "索引器未初始化，无法检索情报数据。",
                "item_count": 0,
                "source_count": 0,
            }

        seen: set[str] = set()
        relevant: list[dict] = []
        source_set: set[str] = set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        for material in selected_materials:
            if not isinstance(material, dict):
                continue
            material_id = str(material.get("id", ""))
            if material_id and material_id in seen:
                continue
            if material_id:
                seen.add(material_id)
            sources = [material.get("source", ""), *(material.get("sources") or [])]
            for src in sources:
                if src:
                    source_set.add(str(src))
            relevant.append({
                "title": str(material.get("title", ""))[:160],
                "content": str(material.get("summary", ""))[:500],
                "source": ", ".join(str(src) for src in sources if src) or "selected",
                "date": str(material.get("date", ""))[:10],
                "layer": str(material.get("layer", "")) or "selected",
            })

        if selected_materials:
            docs = []
        elif indexer is None:
            docs = []
        else:
            docs = indexer.get_all()

        for doc in docs:
            text = doc.text
            if not text:
                continue
            body_hash = hashlib.md5(text.encode()).hexdigest()
            if body_hash in seen:
                continue
            seen.add(body_hash)

            captured_raw = doc.captured_at
            if captured_raw:
                try:
                    dt = datetime.fromisoformat(captured_raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                except ValueError:
                    continue

            ext = doc.extensions or {}
            title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]

            combined = (title + " " + text[:500]).lower()
            if topic and topic.lower() not in combined and topic not in combined:
                continue
            if country:
                loc = extract_location(text)
                if loc is None or loc[0] != country:
                    continue

            layer = _get_layer(doc)
            if layer_filter and layer.value != layer_filter:
                continue

            src_name = doc.source_system or doc.collector_id
            source_set.add(src_name)
            relevant.append({
                "title": title.split("\n")[0],
                "content": text[:500],
                "source": src_name,
                "date": doc.captured_at[:10] if doc.captured_at else "",
                "layer": layer.value,
            })

            if len(relevant) >= max_items:
                break

        topic_desc = topic or country or "全局态势"

        if not relevant:
            return {
                "title": f"态势简报：{topic_desc}",
                "summary": "指定条件下无可用情报数据。",
                "item_count": 0,
                "source_count": 0,
            }

        context_lines = []
        for i, r in enumerate(relevant, 1):
            context_lines.append(
                f"[{i}] {r['date']} | {r['source']} | {r['layer']}\n"
                f"    标题: {r['title']}\n"
                f"    内容: {r['content'][:300]}\n"
            )
        context = "\n".join(context_lines)
        user_prompt = f"## 情报数据（{len(relevant)}条）\n\n{context}\n\n## 简报主题\n\n{topic_desc}\n\n请生成结构化中文态势简报。"

        template_report = _build_template_report(topic_desc, relevant, len(source_set))
        if os.getenv("REPORT_LLM_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
            return template_report

        result = await self._call_llm(_SYSTEM_REPORT, user_prompt)

        if not result:
            return template_report

        lines = result.split("\n")
        summary = ""
        sections = []
        current_heading = ""
        current_body: list[str] = []
        for line in lines:
            if line.startswith("## "):
                if current_heading:
                    sections.append({"heading": current_heading, "body": "\n".join(current_body).strip()})
                current_heading = line
                current_body = []
            elif line.strip() and not summary:
                summary = line.strip()
            else:
                current_body.append(line)
        if current_heading:
            sections.append({"heading": current_heading, "body": "\n".join(current_body).strip()})

        return {
            "title": f"态势简报：{topic_desc}",
            "summary": summary or f"共{len(relevant)}条情报，来自{len(source_set)}个来源",
            "sections": sections,
            "item_count": len(relevant),
            "source_count": len(source_set),
        }
