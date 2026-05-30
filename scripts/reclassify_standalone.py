"""Standalone reclassification script — runs outside FastAPI process.

Reads all bronze JSON files, runs LLM classification on each doc without
a stored layer, and writes the result back. Safe to run while the API is live.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Load .env before reading config
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    import dotenv
    dotenv.load_dotenv(_ENV_PATH)

# ── Config ──
STORAGE = Path(os.environ.get("BRONZE_STORAGE", "/opt/osint-network/bronze_storage"))
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

MAX_INPUT_LENGTH = 3000
MAX_RETRIES = 2

SYSTEM_PROMPT = (
    "You are an intelligence classification expert. "
    "Classify the given text into EXACTLY ONE category. "
    "Return ONLY the category key (one word), nothing else — no explanation, no punctuation.\n\n"
    "Categories:\n"
    "- nature: Natural disasters, climate, weather, environment, ecology, biodiversity, pollution\n"
    "- commerce: Business operations, companies, startups, mergers, manufacturing, industry, retail\n"
    "- finance: Financial markets, currencies, interest rates, stocks, bonds, inflation, GDP, monetary policy\n"
    "- people: Politics, governance, elections, diplomacy, society, culture, education, public health, protests\n"
    "- military: Armed forces, weapons, defense, wars, combat, military exercises, troop deployments\n"
    "- aviation: Civil aviation, airlines, aircraft, airports, aerospace, space exploration, satellites\n"
    "- logistics: Transportation, shipping, freight, ports, warehousing, delivery, rail, trucking\n"
    "- trade: International trade POLICY, tariffs, customs, trade agreements, sanctions, embargoes, dumping\n"
    "- ai4s: AI applied TO scientific research — drug discovery, protein folding, materials science, climate modeling\n"
    "- ai: AI technology/industry — LLMs, ChatGPT, generative AI, AI chips, AI startups, AI regulation\n\n"
    "Disambiguation rules:\n"
    "- Trade POLICY (tariffs, trade wars, FTAs, customs rules) → trade. Business OPERATIONS (company sales, factory output) → commerce.\n"
    "- Shipping/transport/supply-chain operations → logistics. Trade agreements/tariffs → trade.\n"
    "- Military drones/combat UAVs → military. Civilian/commercial drones/delivery drones → aviation or logistics.\n"
    "- AI used FOR scientific discovery (drug design, protein prediction) → ai4s. News ABOUT AI industry (new chatbot, GPU chips) → ai.\n"
    "- Financial sanctions → finance. Trade sanctions/embargoes → trade.\n"
    "- If multiple categories match, pick the MOST SPECIFIC one."
)

VALID_LAYERS = {
    "nature", "commerce", "finance", "people", "military",
    "aviation", "logistics", "trade", "ai4s", "ai",
}


async def classify_one(client: httpx.AsyncClient, title: str, content: str) -> str | None:
    text = f"TITLE: {title[:500]}\n\nCONTENT: {content[:MAX_INPUT_LENGTH]}"
    if not text.strip():
        return "people"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "max_tokens": 16,
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if r.status_code == 200:
                result = r.json()
                raw = result["choices"][0]["message"]["content"].strip().lower()
                layer_key = raw.split()[0].strip().rstrip(".,;:!?\"'")
                if layer_key in VALID_LAYERS:
                    return layer_key
                return None
            elif r.status_code == 429:
                await asyncio.sleep(min(2 ** attempt * 5, 30))
            elif r.status_code == 401:
                print(f"  FATAL: API key rejected (401)")
                return None
            else:
                await asyncio.sleep(2 ** attempt)
        except Exception as exc:
            print(f"  Request error (attempt {attempt}): {exc}")
            await asyncio.sleep(2 ** attempt)
    return None


async def main():
    if not LLM_API_KEY:
        print("ERROR: LLM_API_KEY not set")
        sys.exit(1)

    print(f"Storage: {STORAGE}")
    print(f"Model: {LLM_MODEL}")

    # Collect all JSON files
    json_files = sorted(
        p for p in STORAGE.rglob("*.json")
        if p.name not in ("queue.db", "_merge_index.json") and p.stat().st_size > 0
    )
    total = len(json_files)
    print(f"Found {total} JSON files")

    if total == 0:
        print("No files to process")
        return

    # Count already-classified
    need_classify: list[Path] = []
    already = 0
    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            ext = data.get("extensions", {})
            meta = ext.get("horizon_metadata", {}) if isinstance(ext, dict) else {}
            if isinstance(meta, dict) and meta.get("layer"):
                already += 1
            else:
                need_classify.append(fp)
        except (json.JSONDecodeError, OSError):
            continue

    print(f"Already classified: {already}")
    print(f"Need classification: {len(need_classify)}")

    if not need_classify:
        print("All documents already classified!")
        return

    print(f"\nStarting classification (est. {len(need_classify) * 0.5:.0f}s)...\n")

    updated = 0
    failed = 0
    start_time = time.monotonic()

    async with httpx.AsyncClient(timeout=30) as client:
        for i, fp in enumerate(need_classify):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                failed += 1
                continue

            ext = data.get("extensions", {})
            if not isinstance(ext, dict):
                ext = {}
            title = ext.get("horizon_title", "") or ext.get("summary", "") or ""
            content = data.get("body_inline", "") or ""

            layer = await classify_one(client, title, content)
            if layer is None:
                failed += 1
            else:
                h_meta = ext.get("horizon_metadata", {})
                if not isinstance(h_meta, dict):
                    h_meta = {}
                h_meta["layer"] = layer
                ext["horizon_metadata"] = h_meta
                data["extensions"] = ext
                try:
                    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    updated += 1
                except OSError:
                    failed += 1

            # Progress every 50 docs
            if (i + 1) % 50 == 0:
                elapsed = time.monotonic() - start_time
                rate = (i + 1) / elapsed
                remaining = (len(need_classify) - i - 1) / rate
                pct = (already + updated) / total * 100
                print(f"  [{i+1}/{len(need_classify)}] {pct:.0f}% total | "
                      f"updated={updated} failed={failed} | "
                      f"rate={rate:.1f}/s | ETA={remaining:.0f}s")

            await asyncio.sleep(0.3)

    elapsed = time.monotonic() - start_time
    total_classified = already + updated
    print(f"\nDone in {elapsed:.0f}s")
    print(f"Total docs: {total}")
    print(f"LLM classified: {total_classified} ({total_classified/total*100:.0f}%)")
    print(f"Updated this run: {updated}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
