"""ELO ranking system — per-provider, per-model, per-task-type dynamic scoring."""

from __future__ import annotations
import logging
from openblend_public.memory.store import get_store

logger = logging.getLogger("openblend_public.memory.elo")


def record_win(provider: str, model: str, task_type: str = "general") -> float:
    store = get_store()
    new_elo = store.update_elo(provider, model, task_type, won=True)
    logger.info("ELO win: %s/%s [%s] -> %.0f", provider, model, task_type, new_elo)
    return new_elo


def record_loss(provider: str, model: str, task_type: str = "general") -> float:
    store = get_store()
    new_elo = store.update_elo(provider, model, task_type, won=False)
    logger.info("ELO loss: %s/%s [%s] -> %.0f", provider, model, task_type, new_elo)
    return new_elo


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
