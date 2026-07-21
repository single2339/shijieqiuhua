"""USGS, CISA, OpenSky collectors — thin wrappers around public HTTP APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class USGSCollector(BaseAgent):
    agent_id = "usgs_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://earthquake.usgs.gov/fdsnws/event/1/query",
                params={"format": "geojson", "minmagnitude": 2.5, "orderby": "time", "limit": 50},
            )
        data = r.json()
        events = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [0, 0, 0])
            events.append({
                "id": f"usgs-{props.get('id', props.get('code', ''))}",
                "title": f"地震: {props.get('place', '未知')} — M{props.get('mag', '?')}",
                "content": (
                    f"地震{props.get('place', '未知地区')}，"
                    f"震级{props.get('mag', '?')}，深度{coords[2]}km。"
                    f"时间: {props.get('time', '')}。"
                    f"详情: {props.get('url', '')}"
                ),
                "lat": coords[1],
                "lng": coords[0],
                "source": "usgs",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return {"status": "ok", "events": events}


@AgentRegistry.register
class CISACollector(BaseAgent):
    agent_id = "cisa_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            )
        data = r.json()
        vulns = []
        for item in data.get("vulnerabilities", [])[:20]:
            vulns.append({
                "id": f"cisa-{item.get('cveID', '')}",
                "title": f"CVE: {item.get('cveID', '')} — {item.get('vulnerabilityName', '')}",
                "content": (
                    f"漏洞描述: {item.get('shortDescription', '')}。"
                    f"供应商: {item.get('vendorProject', '')}。"
                    f"利用已活跃: {item.get('knownRansomwareCampaignUse', '未知')}。"
                    f"CVE: {item.get('cveID', '')}"
                ),
                "source": "cisa",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return {"status": "ok", "vulnerabilities": vulns}


@AgentRegistry.register
class OpenSkyCollector(BaseAgent):
    agent_id = "opensky_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://opensky-network.org/api/states/all")
        data = r.json()
        states = data.get("states", [])[:50]
        flights = []
        for s in states:
            flights.append({
                "icao24": s[0],
                "callsign": (s[1] or "").strip(),
                "origin_country": s[2],
                "lat": s[6],
                "lng": s[5],
                "altitude": s[7],
                "velocity": s[9],
            })
        return {"status": "ok", "flights_in_view": len(flights), "flights": flights}
