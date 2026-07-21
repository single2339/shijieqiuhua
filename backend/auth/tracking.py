"""User activity tracking — async logging of user actions."""

from __future__ import annotations

import json
import logging
import threading

from backend.auth.db import get_db

log = logging.getLogger(__name__)

ACTION_TYPES = {
    "login",
    "logout",
    "ask_question",
    "generate_report",
    "super_analysis",
    "interpret_analysis",
    "build_embedding_index",
}


def record_activity(user_id: int, action_type: str, details: dict | None = None, ip_address: str = "") -> None:
    # Activity logging must never break the request flow it's attached to: an
    # unrecognized type is logged and skipped, not raised.
    if action_type not in ACTION_TYPES:
        log.warning("record_activity: unknown action_type %r, skipping", action_type)
        return

    details_json = json.dumps(details or {}, ensure_ascii=False)

    def _write():
        try:
            db = get_db()
            db.execute(
                "INSERT INTO user_activities (user_id, action_type, details_json, ip_address) VALUES (?, ?, ?, ?)",
                (user_id, action_type, details_json, ip_address),
            )
            db.commit()
        except Exception:
            pass

    t = threading.Thread(target=_write, daemon=True)
    t.start()
