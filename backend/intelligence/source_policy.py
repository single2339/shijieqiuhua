"""Canonical source identity, tiering, and independence policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from backend.collectors.horizon.models import ContentItem, SourceType
from backend.osint_sources import get_source


class SourceTier(str, Enum):
    PRIMARY = "primary"
    PROFESSIONAL = "professional"
    LOCAL = "local"
    SOCIAL = "social"
    KNOWLEDGE = "knowledge"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceProfile:
    source_key: str
    display_name: str
    tier: SourceTier
    reliability: str
    independence_group: str
    domain: str
    author: str = ""


_PRIMARY_CATEGORIES = {"government", "intl_org"}
_PROFESSIONAL_CATEGORIES = {
    "news_agency", "international", "financial", "military", "defense",
    "cybersecurity", "think_tank", "osint", "environment", "aviation",
    "logistics", "trade", "crypto",
}
_LOCAL_PREFIXES = ("regional_",)
_PROFESSIONAL_PREFIXES = ("financial_",)
_SOCIAL_TYPES = {SourceType.REDDIT, SourceType.TELEGRAM, SourceType.TWITTER}


def _slug(value: str) -> str:
    normalized = re.sub(r"[^\w.:-]+", "-", value.strip().casefold(), flags=re.UNICODE)
    return normalized.strip("-") or "unknown"


def _reliability_letter(credibility: float) -> str:
    if credibility >= 0.88:
        return "A"
    if credibility >= 0.80:
        return "B"
    if credibility >= 0.70:
        return "C"
    if credibility >= 0.60:
        return "D"
    return "E"


class SourceRegistry:
    @classmethod
    def default(cls) -> "SourceRegistry":
        return cls()

    def resolve(self, item: ContentItem) -> SourceProfile:
        metadata = item.metadata or {}
        feed_name = str(metadata.get("feed_name") or "").strip()
        category = str(metadata.get("category") or "").strip().lower()
        author = str(item.author or "").strip()
        declared_independence = str(metadata.get("independence_group") or "").strip()

        if item.source_type in _SOCIAL_TYPES:
            if item.source_type is SourceType.REDDIT:
                channel = str(metadata.get("subreddit") or "unknown")
                source_key = f"reddit:{_slug(channel)}"
            elif item.source_type is SourceType.TELEGRAM:
                channel = str(metadata.get("channel") or feed_name or "unknown")
                source_key = f"telegram:{_slug(channel)}"
            else:
                source_key = f"twitter:{_slug(author)}"
            independence = _slug(declared_independence) if declared_independence else source_key
            return SourceProfile(
                source_key=source_key,
                display_name=source_key,
                tier=SourceTier.SOCIAL,
                reliability="D",
                independence_group=independence,
                domain=category or "social",
                author=author,
            )

        source_key = _slug(feed_name or item.source_type.value)
        config = get_source(source_key)
        effective_category = category or (config.category if config else "")
        if effective_category == "bestblogs":
            tier = SourceTier.KNOWLEDGE
        elif effective_category in _PRIMARY_CATEGORIES:
            tier = SourceTier.PRIMARY
        elif effective_category in _PROFESSIONAL_CATEGORIES:
            tier = SourceTier.PROFESSIONAL
        elif effective_category.startswith(_PROFESSIONAL_PREFIXES):
            tier = SourceTier.PROFESSIONAL
        elif effective_category.startswith(_LOCAL_PREFIXES):
            tier = SourceTier.LOCAL
        elif item.source_type is SourceType.HACKERNEWS:
            tier = SourceTier.KNOWLEDGE
        else:
            tier = SourceTier.UNKNOWN

        credibility = config.credibility if config else {
            SourceTier.PRIMARY: 0.88,
            SourceTier.PROFESSIONAL: 0.82,
            SourceTier.LOCAL: 0.72,
            SourceTier.KNOWLEDGE: 0.65,
            SourceTier.UNKNOWN: 0.50,
        }[tier]
        return SourceProfile(
            source_key=source_key,
            display_name=config.display_name if config else (feed_name or source_key),
            tier=tier,
            reliability=_reliability_letter(credibility),
            independence_group=_slug(declared_independence) if declared_independence else source_key,
            domain=(config.layer_bias if config and config.layer_bias else effective_category or "unknown"),
            author=author,
        )
