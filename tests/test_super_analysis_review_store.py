from __future__ import annotations

import pytest

from backend.agents.intelligence.review_store import InvestigationReviewStore


def test_review_store_is_owner_scoped_and_records_auditable_signoff(tmp_path):
    store = InvestigationReviewStore(tmp_path / "reviews.db")
    pending = store.create_case("request-123", owner_id=7, playbook="event")

    assert pending.status == "pending"
    assert store.get_review("request-123", owner_id=8) is None

    approved = store.submit_review(
        "request-123",
        owner_id=7,
        reviewer_id=7,
        status="approved",
        notes="已核验三项独立来源。",
    )

    assert approved.status == "approved"
    assert approved.reviewer_id == 7
    assert approved.reviewed_at
    assert store.get_review("request-123", owner_id=7) == approved

    with pytest.raises(PermissionError):
        store.submit_review(
            "request-123", owner_id=8, reviewer_id=8, status="rejected", notes="无权操作"
        )
