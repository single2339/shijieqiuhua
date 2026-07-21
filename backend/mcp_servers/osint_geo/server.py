"""OSINT Geo MCP Server — IP geolocation, geocoding, SunCalc, distance.

Run:  python backend/mcp_servers/osint_geo/server.py
Stdio transport — configure in Claude Code settings.json as:
  {"osint-geo": {"command": "python", "args": ["backend/mcp_servers/osint_geo/server.py"]}}
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "osint-geo",
    instructions="OSINT地理空间工具 — IP定位、坐标转换、日照计算、距离测量",
)

# Free tier: 45 req/min, no API key needed
_IP_API_BASE = "http://ip-api.com/json"
_REQUEST_TIMEOUT = 10.0


# ── IP Geolocation ──────────────────────────────────────────────

@mcp.tool()
async def ip_lookup(ip: str) -> dict:
    """查询单个IP的地理位置（国家/城市/ISP/坐标）。

    Args:
        ip: IPv4 或 IPv6 地址
    """
    url = f"{_IP_API_BASE}/{ip}?lang=zh-CN&fields=status,message,country,countryCode,region,regionName,city,lat,lon,isp,org,as,timezone"
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        r = await client.get(url)
        data = r.json()
    if data.get("status") != "success":
        return {"error": data.get("message", "查询失败"), "ip": ip}
    return {
        "ip": ip,
        "country": data.get("country", ""),
        "country_code": data.get("countryCode", ""),
        "region": data.get("regionName", ""),
        "city": data.get("city", ""),
        "lat": data.get("lat", 0.0),
        "lon": data.get("lon", 0.0),
        "isp": data.get("isp", ""),
        "org": data.get("org", ""),
        "as": data.get("as", ""),
        "timezone": data.get("timezone", ""),
    }


@mcp.tool()
async def batch_ip_lookup(ips: list[str]) -> dict[str, dict]:
    """批量查询多个IP的地理位置（最多100个，自动限速）。

    Args:
        ips: IP地址列表
    """
    results: dict[str, dict] = {}
    for i, ip in enumerate(ips[:100]):
        if i > 0:
            await asyncio.sleep(1.5)  # rate limit ~40 req/min
        results[ip] = await ip_lookup(ip)
    return results


# ── Geocoding (Nominatim — OpenStreetMap, free, rate-limited) ────

_NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
_NOMINATIM_UA = "osint-network/1.0"


@mcp.tool()
async def address_to_coordinate(address: str) -> dict:
    """将地址转换为经纬度坐标（正向地理编码，基于 OpenStreetMap）。

    Args:
        address: 地址字符串，如 "北京市海淀区中关村"
    """
    url = f"{_NOMINATIM_BASE}/search"
    params = {"q": address, "format": "json", "limit": 1, "accept-language": "zh"}
    headers = {"User-Agent": _NOMINATIM_UA}
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        r = await client.get(url, params=params, headers=headers)
        data = r.json()
    if not data:
        return {"address": address, "lat": 0.0, "lon": 0.0, "found": False}
    return {
        "address": address,
        "display_name": data[0].get("display_name", ""),
        "lat": float(data[0].get("lat", 0)),
        "lon": float(data[0].get("lon", 0)),
        "found": True,
    }


@mcp.tool()
async def coordinate_to_address(lat: float, lon: float) -> dict:
    """将经纬度坐标转换为地址（反向地理编码，基于 OpenStreetMap）。

    Args:
        lat: 纬度
        lon: 经度
    """
    url = f"{_NOMINATIM_BASE}/reverse"
    params = {"lat": lat, "lon": lon, "format": "json", "accept-language": "zh"}
    headers = {"User-Agent": _NOMINATIM_UA}
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        r = await client.get(url, params=params, headers=headers)
        data = r.json()
    return {
        "lat": lat,
        "lon": lon,
        "display_name": data.get("display_name", ""),
        "address": data.get("address", {}),
    }


# ── SunCalc (pure Python, no API) ────────────────────────────────

@mcp.tool()
def sun_position(lat: float, lon: float, date_utc: str = "") -> dict:
    """计算指定日期和位置的太阳位置（方位角、高度角、日出日落时间）。

    由阴影方向和长度可用于推断照片拍摄时间和验证地理位置。

    Args:
        lat: 纬度
        lon: 经度
        date_utc: UTC日期时间，格式 YYYY-MM-DDTHH:MM，默认now
    """
    if date_utc:
        dt = datetime.fromisoformat(date_utc).replace(tzinfo=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    # Julian date
    jd = _to_julian(dt)
    # Solar position
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    ecliptic_lon = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    obliquity = math.radians(23.439 - 0.0000004 * n)

    # Declination
    dec = math.asin(math.sin(obliquity) * math.sin(ecliptic_lon))
    # Right ascension
    ra = math.atan2(math.cos(obliquity) * math.sin(ecliptic_lon), math.cos(ecliptic_lon))

    # Hour angle
    gmst = (280.46061837 + 360.98564736629 * n) % 360
    lmst = math.radians((gmst + lon) % 360)
    ha = lmst - ra

    lat_rad = math.radians(lat)
    # Altitude
    alt = math.asin(math.sin(lat_rad) * math.sin(dec) + math.cos(lat_rad) * math.cos(dec) * math.cos(ha))
    alt_deg = round(math.degrees(alt), 2)
    # Azimuth
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(lat_rad) - math.sin(lat_rad) * math.cos(ha))
    az_deg = round((math.degrees(az) + 360) % 360, 2)

    # Sunrise/sunset approximation
    ha_sunrise = math.acos(
        max(-1, min(1, (math.sin(math.radians(-0.833)) - math.sin(lat_rad) * math.sin(dec))
        / (math.cos(lat_rad) * math.cos(dec))))
    )
    noon_jd = jd - (jd % 1) + 0.5 - lon / 360.0
    sunrise_jd = noon_jd - math.degrees(ha_sunrise) / 360.0
    sunset_jd = noon_jd + math.degrees(ha_sunrise) / 360.0

    def _jd_to_utc_str(jd_val: float) -> str:
        j = jd_val + 0.5
        f, d = math.modf(j)
        d = int(d)
        h = int(f * 24)
        m = int((f * 24 - h) * 60)
        return f"{h:02d}:{m:02d}"

    return {
        "datetime_utc": dt.isoformat(),
        "lat": lat,
        "lon": lon,
        "sun_altitude_deg": alt_deg,
        "sun_azimuth_deg": az_deg,
        "sunrise_utc": _jd_to_utc_str(sunrise_jd),
        "sunset_utc": _jd_to_utc_str(sunset_jd),
        "daylight": alt_deg > 0,
        "interpretation_hints": {
            "shadow_direction": _shadow_direction(az_deg),
            "shadow_ratio": _shadow_ratio(alt_deg),
        },
    }


def _to_julian(dt: datetime) -> float:
    y, m, d = dt.year, dt.month, dt.day
    if m <= 2:
        y -= 1
        m += 12
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5
    return jd + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0


def _shadow_direction(azimuth: float) -> str:
    dirs = ["北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
             "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北"]
    idx = round(azimuth / 22.5) % 16
    return f"阴影投向 {dirs[idx]}（太阳在相反方向）"


def _shadow_ratio(altitude: float) -> str:
    if altitude <= 0:
        return "太阳在地平线以下"
    ratio = 1.0 / math.tan(math.radians(max(altitude, 1)))
    if ratio < 0.5:
        return f"阴影极短 ({ratio:.1f}:1，太阳接近头顶)"
    elif ratio < 2:
        return f"阴影较短 ({ratio:.1f}:1)"
    elif ratio < 5:
        return f"阴影中等 ({ratio:.1f}:1)"
    else:
        return f"阴影很长 ({ratio:.1f}:1，太阳接近地平线)"


# ── Distance ─────────────────────────────────────────────────────

@mcp.tool()
def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> dict:
    """计算两个坐标点之间的大圆距离（Haversine公式）。

    Args:
        lat1: 点1纬度
        lon1: 点1经度
        lat2: 点2纬度
        lon2: 点2经度
    """
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    km = R * c
    return {
        "point1": {"lat": lat1, "lon": lon1},
        "point2": {"lat": lat2, "lon": lon2},
        "distance_km": round(km, 2),
        "distance_miles": round(km * 0.621371, 2),
        "bearing_deg": round(_bearing(lat1, lon1, lat2, lon2), 1),
    }


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlon = math.radians(lon2 - lon1)
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    y = math.sin(dlon) * math.cos(rlat2)
    x = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# ── Entry Point ──────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
