"""User activity tracking — async logging of user actions."""

from __future__ import annotations

import json
import threading

from backend.auth.db import close_db, get_db

ACTION_TYPES = {
    "login",
    "logout",
    "ask_question",
    "generate_report",
    "super_analysis",
    "interpret_analysis",
}


def record_activity(user_id: int, action_type: str, details: dict | None = None, ip_address: str = "") -> None:
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Unknown action_type: {action_type}")

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
        finally:
            # This runs in a short-lived worker thread; close its thread-local
            # connection so we don't leak one sqlite handle per activity.
            close_db()

    t = threading.Thread(target=_write, daemon=True)
    t.start()
