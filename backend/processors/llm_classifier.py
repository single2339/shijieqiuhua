"""LLM-based intelligence layer classification + location extraction.

Uses DeepSeek to classify content into one of 12 IntelLayers and
extract geographic location from entity/incident references.
Falls back to keyword classifier on any failure.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from backend.llm_config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    CLASSIFY_TIMEOUT,
    create_llm_client,
)
from backend.models import IntelLayer
from backend.processors.classifier import classify as keyword_classify

log = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 3000
MAX_RETRIES = 2
CLASSIFY_DELAY = 0.3

SYSTEM_PROMPT = (
    "You are an intelligence classification and geolocation expert. "
    "Given a piece of intelligence text, do TWO things:\n"
    "1. Classify the text into EXACTLY ONE category.\n"
    "2. Extract the geographic location following the priority rules below.\n\n"
    "Return ONLY a JSON object, nothing else — no explanation, no markdown fences.\n\n"
    "JSON format:\n"
    '{"layer": "<category_key>", "country": "<country_name>", "city": "<city_name or empty>"}\n\n'
    "Categories:\n"
    "- nature: Natural disasters, climate, weather, environment, ecology, biodiversity, pollution, conservation\n"
    "- economy: Business, companies, manufacturing, industry, retail, supply chains, logistics, shipping, freight, startups\n"
    "- finance: Financial markets, currencies, interest rates, stocks, bonds, inflation, GDP, central banks, monetary policy\n"
    "- politics: Elections, governance, diplomacy, international relations, treaties, alliances, trade POLICY, tariffs, sanctions\n"
    "- military: Armed forces, weapons, defense, wars, combat, military exercises, troop deployments, defense procurement\n"
    "- aviation: Civil aviation, airlines, aircraft, airports, air travel, aviation safety, aviation manufacturing\n"
    "- technology: AI, semiconductors, biotech, space exploration, satellites, rockets, quantum computing, general S&T breakthroughs\n"
    "- society: Social movements, protests, education, culture, sports, migration, refugees, demographics, public opinion\n"
    "- energy: Oil, gas, renewables, solar, wind, nuclear power, critical minerals, energy security, OPEC, electricity\n"
    "- agriculture: Food security, crop production, grain trade, fisheries, livestock, food safety, farming policy\n"
    "- health: Pandemics, vaccines, disease outbreaks, healthcare systems, drug regulation, medical research\n"
    "- cyber: Cyber attacks, data breaches, hacking, ransomware, digital sovereignty, information warfare, internet governance\n\n"
    "Disambiguation rules:\n"
    "- Energy POLICY (OPEC decisions, energy sanctions) → energy. Energy MARKETS (oil futures, LNG spot prices) → finance.\n"
    "- Trade POLICY (tariffs, trade wars, FTAs, customs rules) → politics. Trade/export OPERATIONS (company shipments, factory orders) → economy.\n"
    "- Space exploration, satellites, rockets, NASA, SpaceX launches → technology. Civil airlines, airports, Boeing/Airbus → aviation.\n"
    "- Military drones/combat UAVs → military. Civilian drones/delivery drones → technology.\n"
    "- AI research AND AI industry (LLMs, ChatGPT, AI chips, AI startups) → technology (we no longer separate them).\n"
    "- Pandemic outbreak, vaccine development, WHO declarations → health. Healthcare access as social/political issue → politics.\n"
    "- Cyber attacks on military targets → military. Civilian hacking, data breaches, ransomware → cyber.\n"
    "- Supply chain disruption, factory output, shipping rates → economy.\n"
    "- Food PRICES and agricultural COMMODITY markets → finance. Crop production, harvests, food security → agriculture.\n"
    "- If multiple categories match, pick the MOST SPECIFIC one.\n\n"
    "Location extraction rules (CRITICAL):\n"
    "- Priority 1 — Incident location: If the text describes a specific event/action at a specific place, use THAT place.\n"
    "  Examples: '俄军在顿涅茨克推进' → country='乌克兰', city='顿涅茨克'\n"
    "           'Apple opens new office in Bangalore' → country='印度', city='班加罗尔'\n"
    "- Priority 2 — Entity location: If no incident location, use the main entity's base/home country.\n"
    "  Examples: '太初电子获新一轮融资' → country='中国', city='无锡'\n"
    "           'Tesla reports Q2 earnings' → country='美国', city='奥斯汀'\n"
    "- Priority 3 — Fallback: Only if neither can be determined, use country='全球', city=''.\n"
    "  Example: 'Global climate change report released' → country='全球', city=''\n"
    "- Be specific when possible: prefer '上海' over '中国', prefer 'Washington DC' over '美国'.\n"
    "- Use your knowledge of well-known entities (companies, organizations, people) to determine their location.\n"
    "- For country names, use the short Chinese name (中国, 美国, 日本, 英国, etc)."
)


async def classify_with_llm(title: str, content: str) -> tuple[IntelLayer, str, str]:
    """Classify content into an IntelLayer and extract location using LLM.

    Returns (layer, country, city).
    Falls back to keyword-based classifier if LLM is unavailable
    or returns an invalid result.
    """
    if not LLM_API_KEY:
        return (keyword_classify(content), "", "")

    text = f"TITLE: {title[:500]}\n\nCONTENT: {content[:MAX_INPUT_LENGTH]}"
    if not text.strip():
        return (IntelLayer.POLITICS, "", "")

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "max_tokens": 128,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with create_llm_client(timeout=CLASSIFY_TIMEOUT) as client:
                r = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    json=payload,
                )
            if r.status_code == 200:
                result = r.json()
                raw = result["choices"][0]["message"]["content"].strip()

                # Try JSON parse first
                try:
                    data = json.loads(raw)
                    layer_key = data.get("layer", "").strip().lower()
                    country = data.get("country", "").strip()
                    city = data.get("city", "").strip()
                    try:
                        return (IntelLayer(layer_key), country, city)
                    except ValueError:
                        log.warning("LLM classifier returned invalid layer %r in JSON, falling back to keyword", layer_key)
                        return (keyword_classify(content), country, city)
                except json.JSONDecodeError:
                    pass

                # Fallback: parse as plain text (legacy format: "layer_key")
                raw_lower = raw.lower()
                # Strip markdown code fences if present
                if raw_lower.startswith("```"):
                    lines = raw_lower.split("\n")
                    raw_lower = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                layer_key = raw_lower.split()[0].strip().rstrip(".,;:!?\"'")
                try:
                    return (IntelLayer(layer_key), "", "")
                except ValueError:
                    log.warning("LLM classifier returned invalid layer %r, falling back to keyword", raw)
                    return (keyword_classify(content), "", "")

            elif r.status_code == 429:
                backoff = min(2 ** attempt * 5, 30)
                log.warning("LLM classify rate limited (attempt %d/%d), backoff %ds",
                            attempt, MAX_RETRIES, backoff)
                await asyncio.sleep(backoff)
            elif r.status_code == 401:
                log.error("LLM API key rejected (401). Check LLM_API_KEY.")
                return (keyword_classify(content), "", "")
            else:
                log.warning("LLM classify HTTP %d (attempt %d/%d)",
                            r.status_code, attempt, MAX_RETRIES)
                await asyncio.sleep(2 ** attempt)
        except Exception as exc:
            log.warning("LLM classify request failed (%s) attempt %d/%d",
                        exc, attempt, MAX_RETRIES)
            await asyncio.sleep(2 ** attempt)

    return (keyword_classify(content), "", "")
