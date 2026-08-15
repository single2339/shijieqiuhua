from __future__ import annotations

"""Compatibility entrypoint for the ShijieQiuhua football API.

The production service is defined in :mod:`backend.app_football`.  This module
keeps older imports such as ``from backend.main import app`` working without
restarting the removed generic OSINT Network/Horizon application stack.
"""

from backend.app_football import app

__all__ = ["app"]
