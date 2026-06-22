"""Tests for backend.football_osint.track_record."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.auth import db as auth_db


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir(parents=True)
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    return auth_db.get_db()


def test_prediction_record_table_exists(tmp_db):
    row = tmp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prediction_record'"
    ).fetchone()
    assert row is not None
