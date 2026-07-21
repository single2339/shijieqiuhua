"""Agent configuration loader — YAML + env var overrides."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"

_agent_config: dict[str, dict] = {}
_loaded = False


def load_agent_config(agent_id: str) -> dict:
    global _agent_config, _loaded
    if not _loaded:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            _agent_config = data.get("agents", {})
        _loaded = True

    cfg = dict(_agent_config.get(agent_id, {}))
    prefix = f"AGENT_{agent_id.upper()}_"
    for key, env_key in [("model", f"{prefix}MODEL"), ("max_tokens", f"{prefix}MAX_TOKENS")]:
        val = os.environ.get(env_key)
        if val:
            try:
                cfg[key] = type(cfg.get(key, ""))(val)
            except (ValueError, TypeError):
                cfg[key] = val
    return cfg


def is_agent_mode() -> bool:
    return os.environ.get("AGENT_MODE", "true").lower() == "true"
