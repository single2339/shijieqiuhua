"""Market collection results assembled independently from OSINT prediction."""
from __future__ import annotations

from datetime import datetime

from .adapters import sporttery as sporttery_adapter
from .analysis.market import build_market_consensus
from .models import (
    MarketContext,
    MarketHandicapSnapshot,
    MarketSourceSnapshot,
    OsintSourceStatus,
    SportteryMarket,
)


def build_market_context(
    sporttery_market: SportteryMarket | None,
    licensed_snapshots: list[MarketSourceSnapshot],
    *,
    now: datetime | None = None,
) -> MarketContext:
    """Combine validated sources while retaining Sporttery's HHAD snapshot."""
    snapshots = list(licensed_snapshots)
    handicap_snapshots: list[MarketHandicapSnapshot] = []
    if sporttery_market is not None:
        try:
            observed_at = datetime.fromisoformat(sporttery_market.observed_at.replace("Z", "+00:00"))
        except ValueError:
            observed_at = None
        if observed_at is None or observed_at.tzinfo is None or observed_at.utcoffset() is None:
            return MarketContext(
                snapshots=snapshots,
                consensus=build_market_consensus(snapshots, now=now),
            )
        source_snapshot = sporttery_adapter.market_source_snapshot(
            sporttery_market,
            observed_at=observed_at,
        )
        if source_snapshot is not None:
            snapshots.insert(0, source_snapshot)
        if (
            sporttery_market.home_handicap is not None
            and sporttery_market.hhad_odds is not None
            and sporttery_market.hhad_implied_probabilities is not None
        ):
            handicap_snapshots.append(
                MarketHandicapSnapshot(
                    source_id=sporttery_market.provider,
                    home_handicap=sporttery_market.home_handicap,
                    odds=sporttery_market.hhad_odds,
                    implied_probabilities=sporttery_market.hhad_implied_probabilities,
                    observed_at=observed_at,
                )
            )
    return MarketContext(
        snapshots=snapshots,
        handicap_snapshots=handicap_snapshots,
        consensus=build_market_consensus(snapshots, now=now),
    )


def licensed_market_source_status(
    snapshots: list[MarketSourceSnapshot],
    reason: str,
) -> OsintSourceStatus:
    """Expose licensed-market availability without blocking OSINT research."""
    if snapshots:
        return OsintSourceStatus(
            adapter="theoddsapi",
            label="主流博彩网站胜率",
            status="ok",
        )
    return OsintSourceStatus(
        adapter="theoddsapi",
        label="主流博彩网站胜率",
        status="failed" if reason.endswith("请求失败") or reason.endswith("请求超时") or reason.endswith("响应无效") else "skipped",
        reason=reason,
    )
