"""Lightweight LLM helper for football Q&A.

Uses the same DeepSeek API as the rest of the project.
"""
from __future__ import annotations

import os

import httpx

_TIMEOUT = 30.0


def answer_question(question: str, evidence_text: str, match_context: str) -> str:
    """Ask the LLM to answer a specific football question based on collected evidence.

    Returns a concise Chinese answer, or empty string on failure.
    """
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key:
        return ""

    system = (
        "你是一个足球情报分析师。根据下面提供的比赛证据和数据，"
        "用简洁的中文（2-4句）回答用户的问题。"
        "无论数据是否充分，都必须给出一个明确的方向性结论，不要回避、不要只说“无法判断”。"
        "当证据不足时，照常给出最合理的倾向判断，但要明确提示“本结论数据可靠性较低，仅供参考”，"
        "并简要说明缺少哪些数据。"
        "涉及半场、角球、红黄牌、进球数等可量化的问题时，必须给出具体的预测数值或区间"
        "（例如\"全场角球预计9-11个\"\"黄牌预计3-5张\"），这是你的预测判断，不是引用情报原文，"
        "即使情报里没有现成数字也要给出区间。"
        "但不得把不存在的内容包装成已确认的事实，也不得编造具体的历史比赛比分或引述来源。"
        "不要给出投注建议。"
    )

    user = (
        f"比赛信息：{match_context}\n\n"
        f"已收集的证据：\n{evidence_text}\n\n"
        f"用户问题：{question}"
    )

    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 300,
                "temperature": 0.3,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""
