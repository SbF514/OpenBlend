"""SQLite storage for pre-trained ELO rankings."""

from __future__ import annotations
import logging
import sqlite3
from pathlib import Path
from typing import Any

from openblend_public.config import get_config

logger = logging.getLogger("openblend_public.memory.store")

_DDL = """
CREATE TABLE IF NOT EXISTS provider_elo (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT "general",
    elo REAL NOT NULL DEFAULT 1200.0,
    wins INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, model, task_type)
);
CREATE TABLE IF NOT EXISTS recipe_elo (
    recipe_hash TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT "general",
    elo REAL NOT NULL DEFAULT 1200.0,
    wins INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    node_types TEXT NOT NULL DEFAULT "",
    PRIMARY KEY (recipe_hash, task_type)
);
"""


class TraceStore:
    def __init__(self, db_path: Path | None = None):
        cfg = get_config()
        self._path = db_path if db_path else cfg.trained_db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        return self._conn

    def get_elo_rankings(self, task_type: str = "general") -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT provider, model, elo, wins, total FROM provider_elo WHERE task_type=? ORDER BY elo DESC",
            (task_type,)
        ).fetchall()
        return [
            {"provider": r[0], "model": r[1], "elo": r[2], "wins": r[3], "total": r[4]}
            for r in rows
        ]

    def get_recipe_rankings(self, task_type: str = "general") -> list[dict[str, Any]]:
        """Get recipe ELO rankings."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT recipe_hash, elo, wins, total, node_types FROM recipe_elo "
            "WHERE task_type=? ORDER BY elo DESC",
            (task_type,)
        ).fetchall()
        return [
            {
                "recipe_hash": r[0],
                "elo": r[1],
                "wins": r[2],
                "total": r[3],
                "node_types": r[4]
            }
            for r in rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


_store: TraceStore | None = None


def get_store() -> TraceStore:
    global _store
    if _store is None:
        _store = TraceStore()
    return _store
