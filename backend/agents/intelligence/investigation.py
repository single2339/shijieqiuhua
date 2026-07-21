"""Deterministic OSINT investigation playbooks and traceable evidence ledger.

Playbooks produce leads and collected artefacts.  They never turn a tool result
or a search result into a verified conclusion on their own.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import urlparse

from backend.models import (
    AlternativeExplanation,
    CollectionTask,
    InvestigationEvidence,
    InvestigationPendingVerification,
    InvestigationPlan,
    InvestigationRelationshipEdge,
    InvestigationRelationshipGraph,
    InvestigationRelationshipNode,
    InvestigationResult,
    InvestigationTimelineEntry,
)

Tool = Callable[..., Awaitable[dict[str, Any]]]
CapturePage = Callable[[str], Awaitable[dict[str, Any]]]
CaptureImage = Callable[[str], Awaitable[dict[str, Any]]]
ReverseImageSearch = Callable[[str], Awaitable[dict[str, Any] | None]]


_PLAYBOOKS: dict[str, tuple[list[str], list[str]]] = {
    "general": (
        ["检索内部情报索引", "收集未验证公开搜索线索"],
        ["核对原始来源与发布时间", "对关键命题取得三项独立来源"],
    ),
    "person": (
        ["检索公开网页与已授权平台线索", "收集公开活动时间线"],
        ["核对账号归属的至少两项独立公开信号", "由分析师复核敏感关联"],
    ),
    "website": (
        ["WHOIS、DNS、ICP 查询", "反向 IP 与服务器地理信息", "受控页面快照"],
        ["核对域名历史", "核对注册主体与页面声明", "确认共同标识符不是托管服务造成"],
    ),
    "image": (
        ["提取图片文件元数据", "查询已配置的反向搜图服务", "记录可见地标、文字和时间线索"],
        ["核对元数据是否可伪造", "以独立地理和时间证据复核"],
    ),
    "identity": (
        ["检索已授权公开身份线索", "比较用户名、简介与公开活动时间线"],
        ["避免仅凭同名关联", "由分析师复核身份匹配阈值"],
    ),
    "event": (
        ["检索内部事件情报", "收集公开多源事件线索", "建立事件时间线"],
        ["核对首发来源与转载链", "交叉验证地点、时间和关键主张"],
    ),
    "threat": (
        ["提取公开 IOC/基础设施线索", "查询域名、DNS 与 IP 上下文"],
        ["核对 IOC 的时间有效性", "避免将共享基础设施直接归因"],
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_domain(target: str) -> str:
    raw = target.strip()
    parsed = urlparse(raw if "://" in raw else f"//{raw}", scheme="https")
    domain = (parsed.hostname or "").rstrip(".").lower()
    if not domain or "." not in domain:
        raise ValueError("website and threat investigations require a valid domain target")
    return domain


def _public_tool_data(value: Any) -> Any:
    """Limit the evidence ledger to demonstrably relevant, non-sensitive output."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if any(token in lower for token in ("email", "phone", "avatar", "raw")):
                continue
            result[str(key)] = _public_tool_data(item)
        return result
    if isinstance(value, list):
        return [_public_tool_data(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:1000]
    return value


def _summary(data: dict[str, Any]) -> str:
    values = []
    for key, value in data.items():
        if key in {"error", "raw", "details"} or value in (None, "", [], {}):
            continue
        values.append(f"{key}={value}")
    return "；".join(values)[:800]


class InvestigationExecutor:
    """Run a bounded playbook and return evidence with provenance.

    Tools can be injected in tests or replaced by a deployment-specific adapter.
    Tool errors are represented in the ledger instead of being silently ignored.
    """

    supported_playbooks = tuple(_PLAYBOOKS)

    def __init__(
        self,
        tools: Mapping[str, Tool] | None = None,
        capture_page: CapturePage | None = None,
        capture_image: CaptureImage | None = None,
        reverse_image_search: ReverseImageSearch | None = None,
    ) -> None:
        self._tools = dict(tools or {})
        self._capture_page = capture_page
        self._capture_image = capture_image
        self._reverse_image_search = reverse_image_search

    def plan_for(self, playbook: str, target: str) -> InvestigationPlan:
        if playbook not in _PLAYBOOKS:
            raise ValueError(f"unsupported investigation playbook: {playbook}")
        collection_steps, verification_steps = _PLAYBOOKS[playbook]
        return InvestigationPlan(
            playbook=playbook,
            target=target,
            collection_steps=collection_steps,
            verification_steps=verification_steps,
        )

    async def run(
        self,
        *,
        playbook: str,
        target: str,
        question: str,
        verification_depth: str = "standard",
        internal_items: list[dict[str, Any]] | None = None,
        web_results: list[dict[str, Any]] | None = None,
    ) -> InvestigationResult:
        if playbook not in _PLAYBOOKS:
            raise ValueError(f"unsupported investigation playbook: {playbook}")
        if playbook == "website":
            result = await self._run_website(target, question, verification_depth)
        elif playbook in {"person", "identity"}:
            result = await self._run_person(playbook, target, question, verification_depth)
        elif playbook == "image":
            result = await self._run_image(target, question, verification_depth)
        elif playbook == "threat":
            result = await self._run_threat(target, question, verification_depth)
        else:
            result = InvestigationResult(
                playbook=playbook,
                scope={"target": target, "question": question, "verification_depth": verification_depth},
                plan=self.plan_for(playbook, target),
                pending_verification=self._pending_for(playbook),
            )
        self._attach_leads(result, target, internal_items or [], web_results or [])
        result.alternative_explanations = self._alternatives_for(playbook)
        result.recommended_next_steps = self._next_steps_for(playbook, target)
        return result

    def _attach_leads(
        self,
        result: InvestigationResult,
        target: str,
        internal_items: list[dict[str, Any]],
        web_results: list[dict[str, Any]],
    ) -> None:
        lead_evidence: list[InvestigationEvidence] = []
        for index, item in enumerate(internal_items):
            document_id = str(item.get("document_id") or item.get("id") or f"internal-{index + 1}")
            source_url = str(item.get("source_url") or item.get("url") or "")
            date = str(item.get("date") or _now())
            lead_evidence.append(InvestigationEvidence(
                id=f"LI{index + 1}", kind="internal_intelligence",
                title=str(item.get("title") or "内部情报"), source=str(item.get("source") or "internal"),
                provenance=f"bronze://{document_id}", collected_at=date,
                verification_status="collected", source_url=source_url,
                summary=str(item.get("content_snippet") or item.get("summary") or "")[:800],
                data={"document_id": document_id},
            ))
        for index, item in enumerate(web_results):
            url = str(item.get("url") or "")
            lead_evidence.append(InvestigationEvidence(
                id=f"LW{index + 1}", kind="web_search_lead",
                title=str(item.get("title") or url or "公开搜索线索"), source="web-search",
                provenance=url or f"search://lead/{index + 1}", collected_at=_now(),
                verification_status="unverified", source_url=url,
                summary=str(item.get("snippet") or "")[:800],
            ))
        if not lead_evidence:
            return
        result.evidence.extend(lead_evidence)
        self._add_lead_relationships(result.relationship_graph, target, lead_evidence)
        result.timeline = self._timeline_for(result.evidence)

    @staticmethod
    def _add_lead_relationships(
        graph: InvestigationRelationshipGraph,
        target: str,
        evidence: list[InvestigationEvidence],
    ) -> None:
        target_id = f"target:{target or 'question'}"
        if not any(node.id == target_id for node in graph.nodes):
            graph.nodes.append(InvestigationRelationshipNode(
                id=target_id, label=target or "调查问题", type="target",
            ))
        for item in evidence:
            source_id = f"evidence:{item.id}"
            graph.nodes.append(InvestigationRelationshipNode(
                id=source_id, label=item.title, type=item.kind,
            ))
            graph.edges.append(InvestigationRelationshipEdge(
                source=source_id, target=target_id,
                relation="reports_on" if item.kind == "internal_intelligence" else "leads_to",
                evidence_ids=[item.id],
            ))

    @staticmethod
    def _timeline_for(evidence: list[InvestigationEvidence]) -> list[InvestigationTimelineEntry]:
        grouped: dict[str, list[InvestigationEvidence]] = {}
        for item in evidence:
            grouped.setdefault(item.collected_at[:10] or "未知日期", []).append(item)
        return [
            InvestigationTimelineEntry(
                date=date,
                evidence_ids=[item.id for item in items],
                summary=f"{len(items)} 条证据或线索记录",
            )
            for date, items in sorted(grouped.items())
        ]

    async def _resolve_tool(self, name: str) -> Tool:
        if name in self._tools:
            return self._tools[name]
        if name == "whois_lookup":
            from backend.mcp_servers.osint_whois.server import whois_lookup
            return whois_lookup
        if name == "dns_all_records":
            from backend.mcp_servers.osint_whois.server import dns_all_records
            return dns_all_records
        if name == "icp_lookup":
            from backend.mcp_servers.osint_whois.server import icp_lookup
            return icp_lookup
        if name == "reverse_ip_lookup":
            from backend.mcp_servers.osint_whois.server import reverse_ip_lookup
            return reverse_ip_lookup
        if name == "ip_lookup":
            from backend.mcp_servers.osint_geo.server import ip_lookup
            return ip_lookup
        if name == "weibo_search":
            from backend.mcp_servers.osint_weibo.server import weibo_search
            return weibo_search
        raise ValueError(f"tool is not configured: {name}")

    async def _call(self, name: str, *args: Any) -> dict[str, Any]:
        try:
            tool = await self._resolve_tool(name)
            result = await tool(*args)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            return {"error": f"{name}_unavailable", "detail": str(exc)[:200]}

    @staticmethod
    def _evidence(
        identifier: str,
        kind: str,
        title: str,
        source: str,
        provenance: str,
        data: dict[str, Any],
        *,
        source_url: str = "",
    ) -> InvestigationEvidence:
        failed = bool(data.get("error"))
        return InvestigationEvidence(
            id=identifier,
            kind=kind,
            title=title,
            source=source,
            provenance=provenance,
            collected_at=_now(),
            verification_status="failed" if failed else "collected",
            summary=_summary(data),
            source_url=source_url,
            data=_public_tool_data(data),
        )

    async def _run_website(
        self,
        target: str,
        question: str,
        verification_depth: str,
    ) -> InvestigationResult:
        domain = _normalise_domain(target)
        whois, dns, icp = await asyncio.gather(
            self._call("whois_lookup", domain),
            self._call("dns_all_records", domain),
            self._call("icp_lookup", domain),
        )
        evidence = [
            self._evidence("E1", "whois", "WHOIS 注册信息", "osint-whois", "mcp://osint-whois/whois_lookup", whois),
            self._evidence("E2", "dns", "DNS 记录", "osint-whois", "mcp://osint-whois/dns_all_records", dns),
            self._evidence("E3", "icp", "ICP备案信息", "osint-whois", "mcp://osint-whois/icp_lookup", icp),
        ]
        reverse = await self._call("reverse_ip_lookup", domain)
        evidence.append(self._evidence(
            "E4", "reverse_ip", "反向 IP 关联", "osint-whois",
            "mcp://osint-whois/reverse_ip_lookup", reverse,
        ))

        addresses = (dns.get("summary") or {}).get("A") or []
        address = str(addresses[0]) if addresses else ""
        if address:
            geo = await self._call("ip_lookup", address)
            evidence.append(self._evidence(
                "E5", "ip_geolocation", "IP 地理信息", "osint-geo",
                "mcp://osint-geo/ip_lookup", geo,
            ))

        capture = self._capture_page
        if capture is None:
            from backend.agents.intelligence.controlled_fetch import capture_public_page
            capture = capture_public_page
        if capture:
            capture_url = f"https://{domain}"
            try:
                captured = await capture(capture_url)
            except Exception as exc:
                captured = {"error": "page_capture_unavailable", "detail": str(exc)[:200]}
            artifact = self._evidence(
                "E6", "web_snapshot", "受控网页快照", "controlled-fetch",
                "controlled-fetch://snapshot", captured,
                source_url=str(captured.get("final_url") or captured.get("url") or capture_url),
            )
            if not captured.get("error"):
                artifact.verification_status = str(captured.get("verification_status") or "captured")
                artifact.content_sha256 = str(captured.get("content_sha256") or "")
            evidence.append(artifact)

        graph = self._website_graph(domain, whois, dns, icp, reverse, evidence)
        return InvestigationResult(
            playbook="website",
            scope={"target": domain, "question": question, "verification_depth": verification_depth},
            plan=self.plan_for("website", domain),
            evidence=evidence,
            relationship_graph=graph,
            timeline=[InvestigationTimelineEntry(
                date=_now()[:10],
                evidence_ids=[item.id for item in evidence],
                summary="本次调查采集与快照时间点",
            )],
            pending_verification=self._pending_for("website"),
            errors=[item.data.get("error", "") for item in evidence if item.data.get("error")],
        )

    async def _run_person(
        self,
        playbook: str,
        target: str,
        question: str,
        verification_depth: str,
    ) -> InvestigationResult:
        social = await self._call("weibo_search", target, 20)
        evidence = [self._evidence(
            "E1", "social_search", "公开平台搜索线索", "osint-weibo",
            "mcp://osint-weibo/weibo_search", social,
        )]
        # A platform search is a lead, not proof that the returned account is
        # the named individual.  Identity claims require independent review.
        if evidence[0].verification_status != "failed":
            evidence[0].verification_status = "unverified"
        target_id = f"person:{target}"
        graph = InvestigationRelationshipGraph(
            nodes=[InvestigationRelationshipNode(id=target_id, label=target, type="person")],
        )
        for index, post in enumerate((social.get("results") or [])[:20]):
            user = str(post.get("user") or post.get("screen_name") or f"公开账号 {index + 1}")
            account_id = f"account:{user}"
            graph.nodes.append(InvestigationRelationshipNode(id=account_id, label=user, type="public_account"))
            graph.edges.append(InvestigationRelationshipEdge(
                source=account_id,
                target=target_id,
                relation="mentions_target",
                evidence_ids=["E1"],
            ))
        return InvestigationResult(
            playbook=playbook,
            scope={"target": target, "question": question, "verification_depth": verification_depth},
            plan=self.plan_for(playbook, target),
            evidence=evidence,
            relationship_graph=graph,
            timeline=self._timeline_for(evidence),
            pending_verification=self._pending_for(playbook),
            errors=[item.data.get("error", "") for item in evidence if item.data.get("error")],
        )

    async def _run_threat(
        self,
        target: str,
        question: str,
        verification_depth: str,
    ) -> InvestigationResult:
        """Passive infrastructure context only; this playbook never scans a host."""
        result = await self._run_website(target, question, verification_depth)
        domain = str(result.scope.get("target") or target)
        result.playbook = "threat"
        result.plan = self.plan_for("threat", domain)
        result.pending_verification = self._pending_for("threat")
        result.scope["passive_only"] = True
        return result

    async def _run_image(
        self,
        target: str,
        question: str,
        verification_depth: str,
    ) -> InvestigationResult:
        capture = self._capture_image
        if capture is None:
            from backend.agents.intelligence.image_forensics import capture_public_image
            capture = capture_public_image
        try:
            metadata = await capture(target)
        except Exception as exc:
            metadata = {"error": "image_capture_unavailable", "detail": str(exc)[:200], "url": target}
        evidence = [self._evidence(
            "E1", "image_metadata", "图片元数据与哈希", "controlled-image",
            "controlled-image://metadata", metadata,
            source_url=str(metadata.get("final_url") or metadata.get("url") or target),
        )]
        if evidence[0].verification_status != "failed":
            evidence[0].verification_status = "captured"
            evidence[0].content_sha256 = str(metadata.get("content_sha256") or "")

        reverse_search = self._reverse_image_search
        if reverse_search is None:
            from backend.agents.intelligence.image_forensics import reverse_image_search
            reverse_search = reverse_image_search
        reverse = await reverse_search(target)
        if reverse is not None:
            reverse_evidence = self._evidence(
                "E2", "reverse_image_search", "反向搜图匹配线索", "reverse-image-search",
                str(reverse.get("provider") or "configured-reverse-search"), reverse,
            )
            if reverse_evidence.verification_status != "failed":
                reverse_evidence.verification_status = "unverified"
            evidence.append(reverse_evidence)

        image_id = f"image:{target}"
        graph = InvestigationRelationshipGraph(nodes=[InvestigationRelationshipNode(
            id=image_id, label=target, type="image",
        )])
        if reverse is not None and not reverse.get("error"):
            for index, match in enumerate((reverse.get("results") or [])[:20]):
                label = str(match.get("title") or match.get("url") or f"相似图片线索 {index + 1}")
                match_id = f"reverse-match:{index + 1}"
                graph.nodes.append(InvestigationRelationshipNode(
                    id=match_id, label=label, type="reverse_image_match",
                ))
                graph.edges.append(InvestigationRelationshipEdge(
                    source=image_id, target=match_id, relation="similar_image_lead", evidence_ids=["E2"],
                ))
        return InvestigationResult(
            playbook="image",
            scope={"target": target, "question": question, "verification_depth": verification_depth},
            plan=self.plan_for("image", target),
            evidence=evidence,
            relationship_graph=graph,
            timeline=self._timeline_for(evidence),
            pending_verification=self._pending_for("image"),
            errors=[item.data.get("error", "") for item in evidence if item.data.get("error")],
        )

    @staticmethod
    def _website_graph(
        domain: str,
        whois: dict[str, Any],
        dns: dict[str, Any],
        icp: dict[str, Any],
        reverse: dict[str, Any],
        evidence: list[InvestigationEvidence],
    ) -> InvestigationRelationshipGraph:
        nodes = [InvestigationRelationshipNode(id=f"domain:{domain}", label=domain, type="domain")]
        edges: list[InvestigationRelationshipEdge] = []

        addresses = (dns.get("summary") or {}).get("A") or []
        for address in addresses[:10]:
            value = str(address)
            node_id = f"ip:{value}"
            nodes.append(InvestigationRelationshipNode(id=node_id, label=value, type="ip"))
            edges.append(InvestigationRelationshipEdge(
                source=f"domain:{domain}", target=node_id, relation="resolves_to", evidence_ids=["E2"],
            ))

        registrant = (whois.get("registrant") or {}).get("organization") or icp.get("company")
        if registrant:
            label = str(registrant)
            node_id = f"organisation:{label}"
            nodes.append(InvestigationRelationshipNode(id=node_id, label=label, type="organisation"))
            edges.append(InvestigationRelationshipEdge(
                source=f"domain:{domain}", target=node_id, relation="registered_to", evidence_ids=["E1", "E3"],
            ))

        for related in (reverse.get("domains") or [])[:100]:
            value = str(related).lower()
            node_id = f"domain:{value}"
            nodes.append(InvestigationRelationshipNode(id=node_id, label=value, type="domain"))
            edges.append(InvestigationRelationshipEdge(
                source=f"domain:{domain}", target=node_id, relation="shares_hosting", evidence_ids=["E4"],
            ))

        snapshot = next((item for item in evidence if item.kind == "web_snapshot"), None)
        for analytics_id in (snapshot.data.get("analytics_ids") if snapshot else []) or []:
            value = str(analytics_id)
            node_id = f"analytics:{value}"
            nodes.append(InvestigationRelationshipNode(id=node_id, label=value, type="analytics_identifier"))
            edges.append(InvestigationRelationshipEdge(
                source=f"domain:{domain}", target=node_id,
                relation="uses_analytics_id", evidence_ids=[snapshot.id],
            ))
        return InvestigationRelationshipGraph(nodes=nodes, edges=edges)

    @staticmethod
    def _pending_for(playbook: str) -> list[InvestigationPendingVerification]:
        questions = {
            "general": ["关键结论是否已有三项独立的一手或高可信来源？"],
            "person": ["账号归属是否经独立公开信号和人工复核确认？"],
            "website": ["域名历史、注册主体和共同标识符是否能由独立历史证据复核？"],
            "image": ["图片元数据、地标与时间线是否由独立材料验证？"],
            "identity": ["身份关联是否排除了同名、共享账号和搬运内容等替代解释？"],
            "event": ["事件首发、时间、地点和关键主张是否能由独立来源交叉验证？"],
            "threat": ["IOC 是否仍有效，且是否排除了共享基础设施导致的错误归因？"],
        }
        return [InvestigationPendingVerification(
            id=f"PV{index + 1}", question=question,
            priority="high" if index == 0 else "medium",
        ) for index, question in enumerate(questions[playbook])]

    @staticmethod
    def _alternatives_for(playbook: str) -> list[AlternativeExplanation]:
        common = [
            AlternativeExplanation(
                id="ALT1",
                explanation="多个报道或线索可能来自同一首发材料，表面上的多源一致不等于独立印证。",
                indicators=["相同措辞", "相同发布时间窗口", "相同引用链"],
            ),
            AlternativeExplanation(
                id="ALT2",
                explanation="观察到的关联可能由共享托管、共同平台或背景事件造成，不足以单独证明控制、归属或因果关系。",
                indicators=["共享基础设施", "平台推荐", "背景事件"],
            ),
        ]
        specific = {
            "person": "同名、搬运内容或公开讨论不构成身份同一性证明。",
            "identity": "相同昵称或头像可能是模仿、重名或共享运营，不构成身份同一性证明。",
            "website": "共用 IP、DNS 或分析标识符可能由 CDN、托管商或第三方服务造成。",
            "image": "EXIF 和图片内容可能被编辑或脱离原始语境，不能单独证明拍摄地点或时间。",
            "event": "时间上的同步不一定表示因果；报道差异也可能来自信息更新速度不同。",
            "threat": "基础设施重合可能来自共享服务，不能单独归因给特定行为者。",
            "general": "检索结果可能受语言、时间窗和来源覆盖度限制。",
        }[playbook]
        common.append(AlternativeExplanation(id="ALT3", explanation=specific, confidence_level="L4"))
        return common

    @staticmethod
    def _next_steps_for(playbook: str, target: str) -> list[CollectionTask]:
        return [
            CollectionTask(
                priority="high",
                task="取得关键主张的原始来源、页面快照和发布时间证据",
                rationale="先确认来源链，避免将转载或搜索摘要当成独立证据。",
                query=target,
            ),
            CollectionTask(
                priority="medium",
                task="补齐至少两项独立来源并复核时间线",
                rationale="满足三源交叉验证并暴露可能的矛盾。",
                query=target,
            ),
        ]
