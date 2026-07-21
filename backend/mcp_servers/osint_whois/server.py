"""OSINT Whois MCP Server — WHOIS, DNS, ICP备案, reverse IP lookup.

Run:  python backend/mcp_servers/osint_whois/server.py
Stdio transport.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
import subprocess
from datetime import datetime

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "osint-whois",
    instructions="OSINT域名与IP情报工具 — WHOIS查询、DNS记录、ICP备案、反向IP",
)

_REQUEST_TIMEOUT = 15.0
_PARSE_TIMEOUT = 10  # seconds for whois subprocess


# ── WHOIS Lookup ─────────────────────────────────────────────────

@mcp.tool()
async def whois_lookup(domain: str) -> dict:
    """查询域名的WHOIS注册信息（注册商、注册/过期日期、名称服务器、注册人）。

    Args:
        domain: 域名，如 example.com
    """
    domain = domain.strip().lower().split("/")[0].split(":")[0]
    if not domain or "." not in domain:
        return {"error": "无效域名", "domain": domain}

    try:
        proc = await asyncio.create_subprocess_exec(
            "whois", domain,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_PARSE_TIMEOUT
        )
        raw = stdout.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        return {"error": "WHOIS查询超时", "domain": domain}
    except FileNotFoundError:
        return {"error": "系统未安装whois命令", "domain": domain}

    if not raw.strip() or "No match for" in raw:
        return {"domain": domain, "registered": False, "raw": raw[:500]}

    return {
        "domain": domain,
        "registered": True,
        "registrar": _extract_whois_field(raw, ["Registrar:", "registrar:"]),
        "creation_date": _extract_whois_field(raw, [
            "Creation Date:", "created:", "Registration Time:",
            "Created on", "Created On",
        ]),
        "expiration_date": _extract_whois_field(raw, [
            "Registry Expiry Date:", "Expiry Date:", "expires:",
            "Expiration Time:", "Expires on", "Expires On",
        ]),
        "updated_date": _extract_whois_field(raw, [
            "Updated Date:", "modified:", "Last Updated on",
        ]),
        "name_servers": _extract_nameservers(raw),
        "registrant": _extract_registrant(raw),
        "status": _extract_whois_status(raw),
    }


def _extract_whois_field(raw: str, keys: list[str]) -> str:
    for key in keys:
        for line in raw.splitlines():
            if line.strip().startswith(key):
                return line.split(":", 1)[-1].strip()
    return ""


def _extract_nameservers(raw: str) -> list[str]:
    ns: list[str] = []
    for line in raw.splitlines():
        if "Name Server:" in line or "nserver:" in line.lower():
            ns.append(line.split(":", 1)[-1].strip().lower())
    return list(dict.fromkeys(ns))


def _extract_registrant(raw: str) -> dict:
    fields = {
        "name": ["Registrant Name:", "person:", "descr:"],
        "organization": ["Registrant Organization:", "org-name:", "org:"],
        "email": ["Registrant Email:", "e-mail:", "Registrant Contact Email:"],
        "phone": ["Registrant Phone:", "phone:", "Registrant Contact Phone:"],
        "country": ["Registrant Country:", "country:"],
    }
    result: dict = {}
    for field, keys in fields.items():
        val = _extract_whois_field(raw, keys)
        if val and val.lower() not in ("redacted for privacy", "not disclosed", ""):
            result[field] = val
    return result


def _extract_whois_status(raw: str) -> list[str]:
    statuses = []
    for line in raw.splitlines():
        if line.strip().startswith("Domain Status:") or "status:" in line.lower():
            s = line.split(":", 1)[-1].strip()
            statuses.append(s)
    return statuses


# ── DNS Lookup (via Cloudflare DoH) ──────────────────────────────

_DOH_BASE = "https://cloudflare-dns.com/dns-query"
_DOH_HEADERS = {"Accept": "application/dns-json"}

_DNS_TYPE_MAP = {
    "A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16,
    "CNAME": 5, "SOA": 6, "PTR": 12, "SRV": 33, "CAA": 257,
}


@mcp.tool()
async def dns_lookup(domain: str, record_type: str = "A") -> dict:
    """查询域名的DNS记录（A/AAAA/MX/NS/TXT/CNAME/SOA/PTR/CAA）。

    使用 Cloudflare DNS-over-HTTPS 获取可靠的全球DNS解析结果。

    Args:
        domain: 域名
        record_type: 记录类型，默认A
    """
    rtype = record_type.upper()
    dns_type = _DNS_TYPE_MAP.get(rtype)
    if dns_type is None:
        return {"error": f"不支持的记录类型: {rtype}", "domain": domain}

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        r = await client.get(
            _DOH_BASE,
            params={"name": domain, "type": str(dns_type)},
            headers=_DOH_HEADERS,
        )
        if r.status_code != 200:
            return {"error": f"DNS查询失败 HTTP {r.status_code}", "domain": domain}
        data = r.json()

    answers = data.get("Answer", [])
    records: list[dict] = []
    for ans in answers:
        records.append({
            "name": ans.get("name", ""),
            "type": _rtype_name(ans.get("type", 0)),
            "ttl": ans.get("TTL", 0),
            "value": ans.get("data", ""),
        })

    return {
        "domain": domain,
        "record_type": rtype,
        "records": records,
        "count": len(records),
    }


@mcp.tool()
async def dns_all_records(domain: str) -> dict:
    """一次性查询域名的所有常见DNS记录类型（A/AAAA/MX/NS/TXT/CNAME/SOA）。

    Args:
        domain: 域名
    """
    types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
    results: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        for rt in types:
            dns_type = _DNS_TYPE_MAP.get(rt, 1)
            try:
                r = await client.get(
                    _DOH_BASE,
                    params={"name": domain, "type": str(dns_type)},
                    headers=_DOH_HEADERS,
                )
                if r.status_code == 200:
                    data = r.json()
                    answers = data.get("Answer", [])
                    results[rt] = {
                        "records": [
                            {"name": a.get("name", ""), "ttl": a.get("TTL", 0),
                             "value": a.get("data", "")}
                            for a in answers
                        ],
                        "count": len(answers),
                    }
            except Exception:
                results[rt] = {"records": [], "count": 0, "error": "查询失败"}

    summary: dict[str, list[str]] = {}
    for rt, result in results.items():
        if result["count"] > 0:
            summary[rt] = [r["value"] for r in result["records"]]

    return {"domain": domain, "summary": summary, "details": results}


def _rtype_name(t: int) -> str:
    for name, num in _DNS_TYPE_MAP.items():
        if num == t:
            return name
    return str(t)


# ── ICP备案查询 ─────────────────────────────────────────────────

@mcp.tool()
async def icp_lookup(domain: str) -> dict:
    """查询中国ICP备案信息（网站主办者、备案号、性质）。

    Args:
        domain: 域名
    """
    domain = domain.strip().lower().split("/")[0].split(":")[0]
    apis: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            r = await client.get(
                "https://api.pearktrue.cn/api/icp.php",
                params={"domain": domain},
            )
            if r.status_code == 200:
                apis.append({"source": "pearktrue", "data": r.json()})
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            r = await client.get(
                "https://api.vvhan.com/api/icp",
                params={"url": domain},
            )
            if r.status_code == 200:
                apis.append({"source": "vvhan", "data": r.json()})
    except Exception:
        pass

    if not apis:
        return {"domain": domain, "error": "ICP查询失败，所有API不可用"}

    merged = _merge_icp_results(apis)
    merged["domain"] = domain
    return merged


def _merge_icp_results(apis: list[dict]) -> dict:
    """Merge ICP lookup results from multiple APIs."""
    icp_no = ""
    company = ""
    nature = ""
    for api in apis:
        data = api["data"]
        if isinstance(data, dict):
            if data.get("icp") or data.get("icp_no"):
                icp_no = icp_no or (data.get("icp") or data.get("icp_no", ""))
            if data.get("company") or data.get("unitName") or data.get("主办单位名称"):
                company = company or (
                    data.get("company") or data.get("unitName") or
                    data.get("主办单位名称", "")
                )
            if data.get("nature") or data.get("natureName") or data.get("单位性质"):
                nature = nature or (
                    data.get("nature") or data.get("natureName") or
                    data.get("单位性质", "")
                )

    result: dict = {"icp_no": icp_no, "company": company, "nature": nature}
    if icp_no:
        result["has_icp"] = True
    else:
        result["has_icp"] = False
        result["note"] = "未查到ICP备案（可能未备案或API不可用）"
    return result


# ── Reverse IP Lookup ────────────────────────────────────────────

@mcp.tool()
async def reverse_ip_lookup(ip_or_domain: str) -> dict:
    """查询同一IP上托管的其他域名（反向IP查询）。

    用于发现可能的关联网站。

    Args:
        ip_or_domain: IP地址或域名
    """
    target = ip_or_domain.strip().lower()

    is_ip = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target)
    if not is_ip:
        try:
            ip = socket.gethostbyname(target)
        except socket.gaierror:
            return {"error": f"无法解析域名: {target}", "input": target}
    else:
        ip = target

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        r = await client.get(
            f"https://api.hackertarget.com/reverseiplookup/",
            params={"q": ip},
        )
        text = r.text.strip()

    if text.startswith("error") or text.startswith("No records"):
        return {"ip": ip, "domains": [], "count": 0, "note": text}

    domains = [d.strip() for d in text.splitlines() if d.strip()]
    return {
        "ip": ip,
        "input": target,
        "domains": domains[:100],
        "count": len(domains),
    }


# ── Entry Point ──────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
