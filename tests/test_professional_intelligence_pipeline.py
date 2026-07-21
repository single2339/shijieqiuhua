from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.collectors.horizon.models import ContentItem, SourceType
from backend.models import IntelLayer
from backend.processors.classifier import classify


def _item(
    *,
    item_id: str,
    title: str,
    content: str,
    source_type: SourceType = SourceType.RSS,
    feed_name: str = "reuters",
    category: str = "news_agency",
) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=source_type,
        title=title,
        content=content,
        url=f"https://example.test/{item_id}",
        author="Reporter Name",
        published_at=datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc),
        metadata={"feed_name": feed_name, "category": category},
    )


def test_default_collection_excludes_general_knowledge_feeds():
    from backend.collectors.horizon_bridge import build_default_rss_feeds

    feeds = build_default_rss_feeds()

    assert feeds
    excluded_categories = {"bestblogs", "ai4s", "ai_hot", "technology", "crypto"}
    assert all(feed.category not in excluded_categories for feed in feeds)


def test_default_collection_disables_generic_hacker_news():
    from backend.collectors.horizon_bridge import _DEFAULT_GITHUB_SOURCES, _DEFAULT_HN_CONFIG

    assert _DEFAULT_HN_CONFIG.enabled is False
    assert all(source.enabled is False for source in _DEFAULT_GITHUB_SOURCES)


def test_unmatched_content_is_unclassified_instead_of_politics():
    assert classify("A practical tutorial for centering a div with CSS grid") is IntelLayer.UNCLASSIFIED


def test_professional_source_identity_is_outlet_not_author():
    from backend.intelligence.source_policy import SourceRegistry, SourceTier

    item = _item(
        item_id="rss-1",
        title="Central bank announces emergency rate decision",
        content="The central bank announced an emergency rate decision after market stress.",
        feed_name="reuters",
    )

    profile = SourceRegistry.default().resolve(item)

    assert profile.source_key == "reuters"
    assert profile.author == "Reporter Name"
    assert profile.tier is SourceTier.PROFESSIONAL
    assert profile.independence_group == "reuters"


def test_social_authors_from_one_community_do_not_count_as_independent_sources():
    from backend.intelligence.source_policy import SourceRegistry

    first = _item(
        item_id="social-a",
        title="Claim A",
        content="An unverified claim from a social community.",
        source_type=SourceType.REDDIT,
        feed_name="",
        category="social",
    )
    second = first.model_copy(update={"id": "social-b", "author": "Another User"})
    first.metadata = {"subreddit": "worldnews"}
    second.metadata = {"subreddit": "worldnews"}
    registry = SourceRegistry.default()

    assert registry.resolve(first).independence_group == registry.resolve(second).independence_group


def test_declared_wire_parent_controls_independence_group():
    from backend.intelligence.source_policy import SourceRegistry

    item = _item(
        item_id="wire-mirror",
        title="Government imposes export ban",
        content="A local outlet republishes a wire report about a government export ban.",
        feed_name="local-mirror",
    )
    item.metadata["independence_group"] = "reuters-wire"

    assert SourceRegistry.default().resolve(item).independence_group == "reuters-wire"


def test_regional_financial_wire_is_tiered_as_professional_source():
    from backend.intelligence.source_policy import SourceRegistry, SourceTier

    item = _item(
        item_id="china-wire",
        title="监管部门发布新的跨境资本规则",
        content="监管部门发布新的跨境资本规则，并明确了实施日期和适用机构。",
        feed_name="cls-telegraph",
        category="financial_china",
    )

    assert SourceRegistry.default().resolve(item).tier is SourceTier.PROFESSIONAL


def test_non_latin_outlet_name_keeps_a_distinct_source_identity():
    from backend.intelligence.source_policy import SourceRegistry

    item = _item(
        item_id="unicode-source",
        title="港口发布临时关闭通知",
        content="港口管理机构发布临时关闭通知，并说明受影响的泊位和恢复评估时间。",
        feed_name="港口观察",
        category="regional_china",
    )

    profile = SourceRegistry.default().resolve(item)

    assert profile.source_key == "港口观察"
    assert profile.independence_group == "港口观察"


def test_actionable_primary_source_event_is_accepted():
    from backend.intelligence.admission import AdmissionEngine, AdmissionStatus
    from backend.intelligence.source_policy import SourceRegistry

    item = _item(
        item_id="official-1",
        title="Authority closes airspace and issues NOTAM for military exercise",
        content=(
            "The aviation authority issued a NOTAM closing the airspace from 08:00 UTC "
            "during a military exercise involving combat aircraft and naval units."
        ),
        feed_name="nato",
        category="government",
    )
    profile = SourceRegistry.default().resolve(item)

    decision = AdmissionEngine().evaluate(item, profile)

    assert decision.status is AdmissionStatus.ACCEPTED
    assert decision.score >= 0.75
    assert decision.event_type == "military_exercise"
    assert decision.layer is IntelLayer.MILITARY
    assert decision.indicator_ids


def test_chinese_language_warning_indicator_is_admitted():
    from backend.intelligence.admission import AdmissionEngine, AdmissionStatus
    from backend.intelligence.source_policy import SourceRegistry

    item = _item(
        item_id="zh-export-control",
        title="政府宣布对关键矿产实施出口管制",
        content=(
            "政府依据新规宣布对稀土、锂等关键矿产实施出口管制，措施立即生效，"
            "海关将暂停未获许可证的相关产品出口，并要求企业重新申报最终用户。"
        ),
        feed_name="cls-telegraph",
        category="financial_china",
    )
    profile = SourceRegistry.default().resolve(item)

    decision = AdmissionEngine().evaluate(item, profile)

    assert decision.status is AdmissionStatus.ACCEPTED
    assert decision.event_type == "export_control"


def test_generic_tutorial_is_quarantined_before_intelligence_processing():
    from backend.intelligence.admission import AdmissionEngine, AdmissionStatus
    from backend.intelligence.source_policy import SourceRegistry, SourceTier

    item = _item(
        item_id="blog-1",
        title="How to build a React form component",
        content="This tutorial explains hooks, validation, CSS layout, and reusable UI components. " * 3,
        feed_name="Smashing Magazine",
        category="bestblogs",
    )
    profile = SourceRegistry.default().resolve(item)

    decision = AdmissionEngine().evaluate(item, profile)

    assert profile.tier is SourceTier.KNOWLEDGE
    assert decision.status is AdmissionStatus.QUARANTINED
    assert "knowledge_source" in decision.reasons
    assert decision.score < 0.55


def test_short_social_comment_cannot_become_an_alert():
    from backend.intelligence.admission import AdmissionEngine, AdmissionStatus
    from backend.intelligence.source_policy import SourceRegistry

    item = _item(
        item_id="reddit-1",
        title="What do you think?",
        content="No source, just a thought.",
        source_type=SourceType.REDDIT,
        feed_name="",
        category="social",
    )
    item.metadata = {"subreddit": "worldnews"}
    profile = SourceRegistry.default().resolve(item)

    decision = AdmissionEngine().evaluate(item, profile)

    assert decision.status is not AdmissionStatus.ACCEPTED
    assert "insufficient_content" in decision.reasons
    assert "social_unverified" in decision.reasons


def test_unknown_source_cannot_self_promote_into_an_alert():
    from backend.intelligence.admission import AdmissionEngine, AdmissionStatus
    from backend.intelligence.source_policy import SourceRegistry

    item = _item(
        item_id="unknown-alert",
        title="Authority closes airspace for military exercise",
        content=(
            "The authority issued a NOTAM closing the airspace from 08:00 UTC during "
            "a military exercise involving combat aircraft and naval units."
        ),
        feed_name="unregistered-source",
        category="",
    )
    profile = SourceRegistry.default().resolve(item)

    decision = AdmissionEngine().evaluate(item, profile)

    assert decision.status is AdmissionStatus.QUARANTINED
    assert "unknown_source" in decision.reasons


@pytest.mark.asyncio
async def test_quarantined_item_skips_expensive_enrichment(monkeypatch):
    import backend.collectors.horizon_bridge as bridge_module
    from backend.intelligence.admission import AdmissionStatus

    item = _item(
        item_id="skip-llm",
        title="How to build a React form component",
        content="A tutorial about hooks, validation, CSS, and reusable components. " * 3,
        feed_name="Smashing Magazine",
        category="bestblogs",
    )
    called = False

    async def _unexpected_processing(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(bridge_module, "_process_item_for_storage", _unexpected_processing)

    profile, decision = await bridge_module._prepare_item_for_storage(item)

    assert called is False
    assert decision.status is AdmissionStatus.QUARANTINED
    assert item.metadata["intelligence_admission"]["status"] == "quarantined"
    assert item.metadata["source_profile"]["source_key"] == profile.source_key


def test_raw_document_uses_canonical_source_identity_not_social_author():
    from backend.agents.collectors._utils import content_item_to_document

    item = _item(
        item_id="reddit-source",
        title="Unverified report of a port closure",
        content="A user claims that a port has closed, but provides no primary evidence.",
        source_type=SourceType.REDDIT,
        feed_name="",
        category="social",
    )
    item.metadata = {
        "subreddit": "worldnews",
        "source_profile": {"source_key": "reddit:worldnews", "author": "Reporter Name"},
    }

    document = content_item_to_document(item)

    assert document.source_system == "reddit:worldnews"
    assert document.extensions["author"] == "Reporter Name"


@pytest.mark.asyncio
async def test_admitted_item_is_persisted_to_bronze_silver_and_gold(tmp_path, monkeypatch):
    import backend.collectors.horizon_bridge as bridge_module
    from backend.intelligence.store import IntelligenceStore
    from src.bronze.writer import BronzeWriter

    item = _item(
        item_id="persist-all-layers",
        title="Authority closes airspace for military exercise",
        content=(
            "The aviation authority issued a NOTAM closing the airspace from 08:00 UTC "
            "during a military exercise involving combat aircraft and naval units."
        ),
        feed_name="nato",
        category="government",
    )

    async def _no_op_processing(value, cache=None):
        return value

    monkeypatch.setattr(bridge_module, "_process_item_for_storage", _no_op_processing)
    profile, decision = await bridge_module._prepare_item_for_storage(item)
    store = IntelligenceStore(tmp_path)

    stored = bridge_module._persist_intelligence_item(
        item,
        profile,
        decision,
        bronze=BronzeWriter(tmp_path),
        intelligence_store=store,
        existing_hashes=set(),
    )

    assert stored is True
    assert len(list(tmp_path.rglob("*.json"))) == 1
    assert len(store.list_points(limit=10)) == 1
    assert len(store.list_events(limit=10)) == 1


@pytest.mark.asyncio
async def test_identical_text_from_independent_sources_is_not_deduplicated(tmp_path, monkeypatch):
    import backend.collectors.horizon_bridge as bridge_module
    from backend.intelligence.store import IntelligenceStore
    from src.bronze.writer import BronzeWriter

    items = [
        _item(
            item_id=f"same-text-{index}",
            title="Government imposes export ban on critical minerals",
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=source,
        )
        for index, source in enumerate(("reuters", "bbc"))
    ]

    async def _no_op_processing(value, cache=None):
        return value

    monkeypatch.setattr(bridge_module, "_process_item_for_storage", _no_op_processing)
    store = IntelligenceStore(tmp_path)
    bronze = BronzeWriter(tmp_path)
    dedupe_keys: set[str] = set()
    stored = []
    for item in items:
        profile, decision = await bridge_module._prepare_item_for_storage(item)
        stored.append(bridge_module._persist_intelligence_item(
            item,
            profile,
            decision,
            bronze=bronze,
            intelligence_store=store,
            existing_hashes=dedupe_keys,
        ))

    assert stored == [True, True]
    event = store.list_events(limit=1)[0]
    assert event["evidence_count"] == 2
    assert event["independent_source_count"] == 2


def test_three_independent_sources_create_one_l1_event(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    sources = ["reuters", "bbc", "guardian"]
    for index, source in enumerate(sources):
        item = _item(
            item_id=f"ban-{index}",
            title="Government imposes export ban on critical minerals",
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=source,
        )
        profile = registry.resolve(item)
        decision = engine.evaluate(item, profile)
        assert decision.accepted
        store.record_document(f"raw-{index}", item, profile, decision)

    events = store.list_events(limit=10)

    assert len(events) == 1
    assert events[0]["confidence_level"] == "L1"
    assert events[0]["independent_source_count"] == 3
    assert events[0]["evidence_count"] == 3
    assert len(store.list_claims(events[0]["event_id"])) == 3


def test_syndicated_sources_do_not_inflate_independent_source_count(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceProfile, SourceTier
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    item_a = _item(
        item_id="wire-a",
        title="Government imposes export ban on critical minerals",
        content="The government imposed an export ban on critical minerals under a new regulation.",
        feed_name="wire-a",
    )
    item_b = item_a.model_copy(update={"id": "wire-b", "url": "https://mirror.test/wire-b"})
    profiles = [
        SourceProfile(
            source_key="wire-a",
            display_name="Wire A",
            tier=SourceTier.PROFESSIONAL,
            reliability="A",
            independence_group="reuters-wire",
            domain="politics",
            author="Reporter A",
        ),
        SourceProfile(
            source_key="wire-b",
            display_name="Wire B",
            tier=SourceTier.PROFESSIONAL,
            reliability="A",
            independence_group="reuters-wire",
            domain="politics",
            author="Reporter B",
        ),
    ]
    for index, (item, profile) in enumerate(zip((item_a, item_b), profiles)):
        decision = engine.evaluate(item, profile)
        assert decision.accepted
        store.record_document(f"raw-wire-{index}", item, profile, decision)

    event = store.list_events(limit=1)[0]

    assert event["evidence_count"] == 2
    assert event["independent_source_count"] == 1
    assert event["confidence_level"] == "L3"


def test_three_low_reliability_sources_cannot_create_l1_confirmation(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceProfile, SourceTier
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    for index in range(3):
        item = _item(
            item_id=f"low-reliability-{index}",
            title="Government imposes export ban on critical minerals",
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=f"unknown-{index}",
        )
        profile = SourceProfile(
            source_key=f"unknown-{index}",
            display_name=f"Unknown {index}",
            tier=SourceTier.PROFESSIONAL,
            reliability="E",
            independence_group=f"unknown-{index}",
            domain="politics",
        )
        store.record_document(f"low-raw-{index}", item, profile, engine.evaluate(item, profile))

    assert store.list_events(limit=1)[0]["confidence_level"] == "L2"


def test_event_identity_uses_original_title_before_source_specific_translation(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    original_title = "Government imposes export ban on critical minerals"
    for index, (source, translated_title) in enumerate((
        ("reuters", "政府宣布关键矿产出口禁令"),
        ("bbc", "当局对关键矿物实施出口限制"),
    )):
        item = _item(
            item_id=f"translated-{index}",
            title=original_title,
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=source,
        )
        profile = registry.resolve(item)
        decision = engine.evaluate(item, profile)
        item.metadata["_original_title"] = original_title
        item.title = translated_title
        store.record_document(f"translated-raw-{index}", item, profile, decision)

    assert len(store.list_events(limit=10)) == 1


def test_non_latin_event_titles_do_not_collapse_into_one_empty_signature(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    for index, title in enumerate((
        "Правительство ограничило экспорт лития",
        "Власти запретили экспорт редкоземельных металлов",
    )):
        item = _item(
            item_id=f"cyrillic-{index}",
            title=title,
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=f"wire-{index}",
        )
        profile = registry.resolve(item)
        store.record_document(f"cyrillic-raw-{index}", item, profile, engine.evaluate(item, profile))

    assert len(store.list_events(limit=10)) == 2


def test_quarantined_document_is_audited_without_creating_intelligence_point(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    item = _item(
        item_id="noise-1",
        title="Ten useful CSS tricks",
        content="A frontend tutorial about layout and typography. " * 4,
        feed_name="Smashing Magazine",
        category="bestblogs",
    )
    profile = SourceRegistry.default().resolve(item)
    decision = AdmissionEngine().evaluate(item, profile)
    store = IntelligenceStore(tmp_path)

    result = store.record_document("raw-noise", item, profile, decision)

    assert result.point_id is None
    assert store.list_events(limit=10) == []
    assert store.get_collection_decision("raw-noise")["status"] == "quarantined"


def test_persisted_gold_events_match_super_analysis_event_contract(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.presentation import build_event_cluster_result
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore
    from backend.models import EventClusterResult

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    for index, source in enumerate(("reuters", "bbc")):
        item = _item(
            item_id=f"contract-{index}",
            title="Government imposes export ban on critical minerals",
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=source,
        )
        profile = registry.resolve(item)
        store.record_document(f"contract-raw-{index}", item, profile, engine.evaluate(item, profile))

    payload = build_event_cluster_result(store, scope={"start_date": "2026-07-21"})
    result = EventClusterResult(**payload)

    assert result.total_clusters == 1
    assert result.clusters[0].confidence.level == "L2"
    assert result.clusters[0].source_count == 2
    assert len(result.clusters[0].claims) == 2
    assert len(result.clusters[0].evidence) == 2
    assert "出口管制" in result.clusters[0].summary
    assert "export_control" not in result.clusters[0].summary
    assert result.clusters[0].claims[0].verification_status == "已获支持"
    assert result.clusters[0].key_terms == ["出口管制"]


def test_persisted_confirmed_military_event_drives_warning_contract(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.presentation import (
        build_event_cluster_result,
        build_warning_indicator_result,
    )
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore
    from backend.models import WarningIndicatorResult

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    for index, source in enumerate(("reuters", "bbc", "guardian")):
        item = _item(
            item_id=f"warning-{index}",
            title="Authority closes airspace for military exercise",
            content=(
                "The aviation authority issued a NOTAM closing the airspace from 08:00 UTC "
                "during a military exercise involving combat aircraft and naval units."
            ),
            feed_name=source,
        )
        profile = registry.resolve(item)
        store.record_document(f"warning-raw-{index}", item, profile, engine.evaluate(item, profile))

    events = build_event_cluster_result(store)
    result = WarningIndicatorResult(**build_warning_indicator_result(events))

    assert result.overall_level == "critical"
    assert result.active_indicator_count == 1
    assert result.indicators[0].related_event_ids == [events["clusters"][0]["id"]]


def test_quality_summary_exposes_admission_and_confidence_distribution(tmp_path):
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    accepted = _item(
        item_id="quality-accepted",
        title="Authority closes airspace for military exercise",
        content=(
            "The authority issued a NOTAM closing the airspace from 08:00 UTC during "
            "a military exercise involving combat aircraft and naval units."
        ),
        feed_name="nato",
        category="government",
    )
    quarantined = _item(
        item_id="quality-quarantine",
        title="Ten useful CSS tricks",
        content="A frontend tutorial about layout and typography. " * 4,
        feed_name="Smashing Magazine",
        category="bestblogs",
    )
    for raw_id, item in (("raw-a", accepted), ("raw-q", quarantined)):
        profile = registry.resolve(item)
        store.record_document(raw_id, item, profile, engine.evaluate(item, profile))

    summary = store.quality_summary()

    assert summary["total_decisions"] == 2
    assert summary["accepted"] == 1
    assert summary["quarantined"] == 1
    assert summary["acceptance_rate"] == 0.5
    assert summary["events_by_confidence"] == {"L3": 1}


@pytest.mark.asyncio
async def test_analysis_events_prefers_persisted_gold_products(tmp_path, monkeypatch):
    import backend.main as main_module
    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    store = IntelligenceStore(tmp_path)
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    for index, source in enumerate(("reuters", "bbc")):
        item = _item(
            item_id=f"api-{index}",
            title="Government imposes export ban on critical minerals",
            content=(
                "The government imposed an export ban on critical minerals including lithium "
                "and rare earth products, effective immediately under a new regulation."
            ),
            feed_name=source,
        )
        profile = registry.resolve(item)
        store.record_document(f"api-raw-{index}", item, profile, engine.evaluate(item, profile))

    monkeypatch.setattr(main_module, "STORAGE", tmp_path)
    result = await main_module.analysis_events(start_date="2026-07-21")

    assert result.total_clusters == 1
    assert result.clusters[0].id == store.list_events(limit=1)[0]["event_id"]


def test_backfill_replays_bronze_without_mutating_raw_documents(tmp_path):
    import hashlib
    import json
    import uuid

    from backend.intelligence.backfill import backfill_intelligence
    from backend.intelligence.store import IntelligenceStore
    from src.bronze.writer import BronzeWriter
    from src.models.document import RawDocument

    body = (
        "The government imposed an export ban on critical minerals including lithium and "
        "rare earth products, effective immediately under a new regulation."
    )
    raw = RawDocument(
        raw_document_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
        channel="web",
        mime_type="text/plain",
        encoding="utf-8",
        body_ref=None,
        body_inline=body,
        headers_summary={},
        captured_at="2026-07-21T08:00:00+00:00",
        collector_id="horizon-rss",
        collector_version="1.0.0",
        source_url="https://example.test/backfill",
        source_system="reuters",
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
        extensions={
            "horizon_title": "Government imposes export ban on critical minerals",
            "horizon_source_type": "rss",
            "horizon_metadata": {"feed_name": "reuters", "category": "news_agency"},
            "published_at": "2026-07-21T08:00:00+00:00",
            "author": "Reporter Name",
        },
    )
    path = BronzeWriter(tmp_path).write(raw)
    before = json.loads(path.read_text(encoding="utf-8"))

    stats = backfill_intelligence(tmp_path)

    assert stats == {"scanned": 1, "accepted": 1, "quarantined": 0, "rejected": 0, "skipped": 0, "errors": 0}
    assert IntelligenceStore(tmp_path).quality_summary()["events"] == 1
    assert json.loads(path.read_text(encoding="utf-8")) == before


def test_intelligence_point_contract_accepts_persisted_product(tmp_path):
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator, FormatChecker

    from backend.intelligence.admission import AdmissionEngine
    from backend.intelligence.source_policy import SourceRegistry
    from backend.intelligence.store import IntelligenceStore

    item = _item(
        item_id="schema-point",
        title="Authority closes airspace for military exercise",
        content=(
            "The authority issued a NOTAM closing the airspace from 08:00 UTC during "
            "a military exercise involving combat aircraft and naval units."
        ),
        feed_name="nato",
        category="government",
    )
    profile = SourceRegistry.default().resolve(item)
    store = IntelligenceStore(tmp_path)
    store.record_document("schema-raw", item, profile, AdmissionEngine().evaluate(item, profile))
    point = store.list_points(limit=1)[0]
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "intelligence-point.schema.json").read_text(encoding="utf-8")
    )

    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(point))

    assert errors == []
