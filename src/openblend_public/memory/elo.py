"""ELO ranking system — per-provider, per-model, per-task-type lookup for pre-trained rankings."""

from __future__ import annotations
import logging
from openblend_public.memory.store import get_store

logger = logging.getLogger("openblend_public.memory.elo")


def get_rankings(task_type: str = "general") -> list[dict]:
    store = get_store()
    return store.get_elo_rankings(task_type) or []


def get_all_categories() -> list[str]:
    store = get_store()
    conn = store._get_conn()
    rows = conn.execute("SELECT DISTINCT task_type FROM provider_elo").fetchall()
    return [r[0] for r in rows]


def best_provider_for(task_type: str = "general") -> tuple[str, str] | None:
    rankings = get_rankings(task_type)
    if not rankings:
        return None
    top = rankings[0]
    return (top["provider"], top["model"])
