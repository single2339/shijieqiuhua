"""Billing domain — activation codes and entitlements.

W1 scope:
- generate_codes(): admin CLI bulk creation
- redeem_code(): user-facing redemption with all 4 error paths
- has_entitlement(): permission check used by routes

W2 will add: API routes wiring, retroactive expiry job, refund flow.

Error codes follow PRD §5.6 naming:
- E_CODE_INVALID            unknown code
- E_CODE_USED               status='used'
- E_CODE_EXPIRED            past expires_at
- E_ENTITLEMENT_DUPLICATE   user already holds same type (does NOT consume code)
"""
from __future__ import annotations

from .service import (
    BillingError,
    EntitlementType,
    generate_codes,
    has_entitlement,
    redeem_code,
)

__all__ = [
    "BillingError",
    "EntitlementType",
    "generate_codes",
    "has_entitlement",
    "redeem_code",
    "billing_router",
]
from .routes import router as billing_router  # noqa: E402
