"""SQLite storage for pre-trained ELO rankings."""

from __future__ import annotations
import logging
import sqlite3
from pathlib import Path
from typing import Any

from openblend_public.config import get_config

logger = logging.getLogger("openblend_public.memory.store")

_DDL = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    prompt_hash TEXT,
    prompt_preview TEXT,
    intent_type TEXT,
    complexity REAL,
    strategy TEXT,
    models_used TEXT,
    judge_score REAL,
    judge_passed INTEGER,
    total_cost REAL,
    latency_ms INTEGER,
    content_preview TEXT
);
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
            self._conn.executescript(_DDL)
        return self._conn

    def update_elo(self, provider: str, model: str, task_type: str, won: bool, k: float = 32.0) -> float:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT elo, wins, total FROM provider_elo WHERE provider=? AND model=? AND task_type=?",
            (provider, model, task_type)
        ).fetchone()
        if row:
            elo, wins, total = row
        else:
            elo, wins, total = 1200.0, 0, 0
        expected = 1.0 / (1.0 + 10**((1200.0 - elo) / 400.0))
        actual = 1.0 if won else 0.0
        new_elo = elo + k * (actual - expected)
        new_wins = wins + (1 if won else 0)
        new_total = total + 1
        conn.execute(
            "INSERT OR REPLACE INTO provider_elo VALUES (?,?,?,?,?,?)",
            (provider, model, task_type, new_elo, new_wins, new_total)
        )
        conn.commit()
        return new_elo

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

    def update_recipe_elo(self, recipe_hash: str, task_type: str, won: bool,
                          node_types: str = "", k: float = 32.0) -> float:
        """Update ELO for a recipe configuration."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT elo, wins, total FROM recipe_elo WHERE recipe_hash=? AND task_type=?",
            (recipe_hash, task_type)
        ).fetchone()
        if row:
            elo, wins, total = row
        else:
            elo, wins, total = 1200.0, 0, 0
        expected = 1.0 / (1.0 + 10**((1200.0 - elo) / 400.0))
        actual = 1.0 if won else 0.0
        new_elo = elo + k * (actual - expected)
        new_wins = wins + (1 if won else 0)
        new_total = total + 1
        conn.execute(
            "INSERT OR REPLACE INTO recipe_elo VALUES (?,?,?,?,?,?)",
            (recipe_hash, task_type, new_elo, new_wins, new_total, node_types)
        )
        conn.commit()
        return new_elo

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
