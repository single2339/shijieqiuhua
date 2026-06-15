"""Open-Meteo weather adapter — free API, no key, zero-config.

PRD §5.5 weather factor; W4 data source expansion.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from ..evidence import append_evidence
from .. import cache
from ..models import FootballOsintJobRequest, OsintEvidence

URL = "https://api.open-meteo.com/v1/forecast"

VENUES: dict[str, tuple[float, float]] = {
    # Asia
    "北京": (39.93,116.44), "beijing": (39.93,116.44), "工体": (39.93,116.44),
    "上海": (31.18,121.44), "shanghai": (31.18,121.44), "虹口": (31.27,121.48),
    "东京": (35.68,139.71), "tokyo": (35.68,139.71),
    "首尔": (37.57,126.90), "seoul": (37.57,126.90),
    "利雅得": (24.73,46.62), "riyadh": (24.73,46.62),
    "多哈": (25.26,51.45), "doha": (25.26,51.45),
    # Europe
    "伦敦": (51.56,-0.28), "london": (51.56,-0.28), "温布利": (51.56,-0.28),
    "巴塞罗那": (41.38,2.16), "barcelona": (41.38,2.16),
    "米兰": (45.48,9.12), "milan": (45.48,9.12),
    "马德里": (40.45,-3.69), "madrid": (40.45,-3.69),
    "慕尼黑": (48.22,11.62), "munich": (48.22,11.62),
    "巴黎": (48.86,2.35), "paris": (48.86,2.35),
    "曼彻斯特": (53.48,-2.24), "manchester": (53.48,-2.24),
    "柏林": (52.52,13.40), "berlin": (52.52,13.40),
    "罗马": (41.93,12.49), "rome": (41.93,12.49),
    "阿姆斯特丹": (52.37,4.90), "amsterdam": (52.37,4.90),
    # South America
    "布宜诺斯艾利斯": (-34.60,-58.38), "buenos aires": (-34.60,-58.38),
    "里约": (-22.91,-43.20), "rio": (-22.91,-43.20),
    "圣保罗": (-23.55,-46.63), "sao paulo": (-23.55,-46.63),
    # 2026 World Cup host cities
    "墨西哥城": (19.43,-99.13), "mexico city": (19.43,-99.13),
    "瓜达拉哈拉": (20.67,-103.35), "guadalajara": (20.67,-103.35),
    "蒙特雷": (25.67,-100.31), "monterrey": (25.67,-100.31),
    "多伦多": (43.65,-79.38), "toronto": (43.65,-79.38),
    "温哥华": (49.28,-123.12), "vancouver": (49.28,-123.12),
    "纽约": (40.71,-74.01), "new york": (40.71,-74.01),
    "洛杉矶": (34.05,-118.24), "los angeles": (34.05,-118.24),
    "达拉斯": (32.78,-96.80), "dallas": (32.78,-96.80),
    "亚特兰大": (33.75,-84.39), "atlanta": (33.75,-84.39),
    "迈阿密": (25.76,-80.19), "miami": (25.76,-80.19),
    "休斯顿": (29.76,-95.37), "houston": (29.76,-95.37),
    "堪萨斯城": (39.10,-94.58), "kansas city": (39.10,-94.58),
    "波士顿": (42.36,-71.06), "boston": (42.36,-71.06),
    "费城": (39.95,-75.17), "philadelphia": (39.95,-75.17),
    "旧金山": (37.77,-122.42), "san francisco": (37.77,-122.42),
    "西雅图": (47.61,-122.33), "seattle": (47.61,-122.33),
}

# Default coordinates by competition when venue is unknown
_COMPETITION_DEFAULTS: dict[str, tuple[float, float]] = {
    "世界杯": (39.10,-94.58),     # Kansas City — central US
    "欧洲预选": (48.86,2.35),     # Paris
    "亚洲预选": (25.26,51.45),    # Doha
    "南美预选": (-23.55,-46.63),  # Sao Paulo
    "欧冠": (48.22,11.62),        # Munich
    "英超": (51.56,-0.28),        # London
    "西甲": (40.45,-3.69),        # Madrid
    "意甲": (45.48,9.12),         # Milan
    "德甲": (52.52,13.40),        # Berlin
    "法甲": (48.86,2.35),         # Paris
    "中超": (39.93,116.44),       # Beijing
    "友谊赛": (48.86,2.35),       # Paris — neutral venue default
}


def collect(request: FootballOsintJobRequest, evidence: list[OsintEvidence]) -> tuple[str, str]:
    coords = _resolve_coords(request)
    if not coords:
        return "", "无法确定场馆坐标，请在 venue 或 notes 中指定 lat:N lon:M"

    lat, lon = coords
    kickoff = (request.kickoff_at or "")[:10]
    if not kickoff:
        from datetime import datetime, timedelta, timezone
        kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    # Try shared weather cache first
    wk = cache.weather_key(lat, lon, kickoff)
    cached = cache.weather_cache.get(wk)
    if cached is not None:
        eid = append_evidence(evidence, source=f"Open-Meteo ({lat},{lon})", source_type="weather",
                              claim=cached, topic="weather.open_meteo", side="neutral",
                              confidence=0.55, raw_excerpt=cached, url="")
        return eid, ""

    params = (
        f"latitude={lat}&longitude={lon}"
        f"&daily=precipitation_probability_max,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,weather_code"
        f"&start_date={kickoff}&end_date={kickoff}&timezone=auto"
    )
    api_url = f"{URL}?{params}"

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "shijieqiuhua/1.0"})
        with urllib.request.urlopen(req, timeout=float(os.getenv("FOOTBALL_OSINT_OPEN_METEO_TIMEOUT", "10"))) as r:
            data: dict[str, Any] = json.loads(r.read().decode())
    except Exception as e:
        return "", f"Open-Meteo: {e}"

    daily = data.get("daily") or {}
    precip = _first(daily, "precipitation_probability_max")
    tmax = _first(daily, "temperature_2m_max")
    tmin = _first(daily, "temperature_2m_min")
    wind = _first(daily, "wind_speed_10m_max")
    wcode = _first(daily, "weather_code")

    WX: dict[tuple, str] = {
        (0,3): "晴/少云", (4,48): "雾/霾", (49,57): "毛毛雨",
        (58,67): "雨", (68,77): "雪", (78,82): "阵雨",
        (83,86): "阵雪", (95,99): "雷暴",
    }
    wx = "未知"
    if wcode is not None:
        for (lo, hi), label in WX.items():
            if lo <= wcode <= hi:
                wx = label
                break

    claim = (
        f"比赛日天气: {wx}，气温 {tmin}–{tmax}°C，"
        f"降水概率 {precip or '?'}%，最大风速 {wind or '?'} km/h"
    )
    eid = append_evidence(evidence, source=f"Open-Meteo ({lat},{lon})", source_type="weather",
                          claim=claim, topic="weather.open_meteo", side="neutral",
                          confidence=0.55, raw_excerpt=json.dumps(data, ensure_ascii=False), url=api_url)
    cache.weather_cache.set(wk, claim)
    return eid, ""


def _resolve_coords(req: FootballOsintJobRequest) -> tuple[float, float] | None:
    text = f"{req.venue or ''} {req.question or ''} {req.competition or ''} {' '.join(req.user_supplied.notes)}".lower()
    # 1. Explicit lat:lon in text
    m = re.search(r"lat:\s*(-?[\d.]+)\s+lon:\s*(-?[\d.]+)", text)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    # 2. Known venue/city name
    for name, coords in VENUES.items():
        if name in text:
            return coords
    # 3. Fallback by competition name
    comp = (req.competition or "").lower()
    for name, coords in _COMPETITION_DEFAULTS.items():
        if name in comp:
            return coords
    return None


def _first(d: dict, k: str) -> int | None:
    vs = d.get(k)
    if not vs or not isinstance(vs, list) or len(vs) == 0:
        return None
    try:
        return int(float(str(vs[0])))
    except (ValueError, TypeError):
        return None
