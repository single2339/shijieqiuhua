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
        "可以给出方向和大致区间，但不得编造具体的虚假数字、比分或引述。"
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
