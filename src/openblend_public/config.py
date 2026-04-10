"""OpenBlend Public configuration — load from blend.yaml + env vars."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from openblend_public.core.types import ModelConfig, ProviderConfig, ProviderSlot, Tier, Transport

logger = logging.getLogger("openblend_public.config")

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_YAML = _ROOT / "blend.yaml"
_TRAINED_DB = _ROOT / "trained" / "blend.db"


@dataclass
class BlendConfig:
    """Central configuration for the OpenBlend Public service."""

    # --- Paths ---
    root_dir: Path = field(default_factory=lambda: _ROOT)
    trained_db_path: Path = field(default_factory=lambda: _TRAINED_DB)

    # --- Providers ---
    providers: list[ProviderConfig] = field(default_factory=list)

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    # --- Blend ---
    default_mode: str = "best"
    judge_pass_threshold: float = 0.75
    max_refine_rounds: int = 2
    monthly_budget: float | None = None

    @property
    def active_providers(self) -> list[ProviderConfig]:
        """Only providers with resolved API keys."""
        return [p for p in self.providers if p.has_key]

    def all_slots(self) -> list[ProviderSlot]:
        """Enumerate all usable (provider, model) slots."""
        slots = []
        for p in self.active_providers:
            for m in p.models:
                slots.append(ProviderSlot(
                    provider=p.name, model=m.id, base_url=p.base_url,
                    api_key=p.api_key, cost_input=m.cost_input,
                    cost_output=m.cost_output, tier=m.tier, timeout=p.timeout,
                    transport=p.transport, cli_bin=p.cli_bin,
                ))

        return slots

    def cheapest_slots(self, n: int = 3) -> list[ProviderSlot]:
        """Get the N cheapest slots for proposing."""
        return sorted(self.all_slots(), key=lambda s: s.cost_output)[:n]

    def strongest_slot(self) -> ProviderSlot | None:
        """Most expensive slot (assumed strongest) for judging."""
        slots = self.all_slots()
        return max(slots, key=lambda s: s.cost_output) if slots else None

    def strongest_http_slot(self) -> ProviderSlot | None:
        """Most expensive HTTP-only slot — avoids CLI timeouts for judging."""
        http_slots = [s for s in self.all_slots() if s.transport == Transport.HTTP]
        return max(http_slots, key=lambda s: s.cost_output) if http_slots else self.strongest_slot()

    def get_provider(self, name: str) -> ProviderConfig | None:
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def list_provider_names(self) -> list[str]:
        return [p.name for p in self.active_providers]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.warning("Config not found: %s — using defaults", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_providers(raw: list[dict[str, Any]]) -> list[ProviderConfig]:
    providers = []
    for p in raw:
        models = []
        for m in p.get("models", []):
            models.append(ModelConfig(
                id=m["id"],
                cost_input=float(m.get("cost_input", 0.0)),
                cost_output=float(m.get("cost_output", 0.0)),
                tier=Tier(m.get("tier", "free")),
            ))
        api_key_env = p.get("api_key_env", "")
        api_key = os.getenv(api_key_env, "") if api_key_env else ""
        transport = Transport(p.get("transport", Transport.HTTP.value))

        providers.append(ProviderConfig(
            name=p["name"], base_url=p.get("base_url", ""),
            api_key_env=api_key_env, api_key=api_key,
            models=models, rate_limit=int(p.get("rate_limit", 60)),
            timeout=int(p.get("timeout", 30)),
            transport=transport,
        ))
    return providers


def load_config(path: Path | None = None) -> BlendConfig:
    """Load configuration from YAML + env vars."""
    load_dotenv(_ROOT / ".env")
    raw = _load_yaml(path or _DEFAULT_YAML)
    providers = _parse_providers(raw.get("providers", []))
    server_raw = raw.get("server", {})
    blend_raw = raw.get("blend", {})

    cfg = BlendConfig(
        providers=providers,
        host=server_raw.get("host", "0.0.0.0"),
        port=int(server_raw.get("port", 8000)),
        debug=server_raw.get("debug", False) or os.getenv("BLEND_DEBUG") == "1",
        cors_origins=server_raw.get("cors_origins", ["*"]),
        default_mode=blend_raw.get("default_mode", "best"),
        judge_pass_threshold=float(blend_raw.get("judge_pass_threshold", 0.75)),
        max_refine_rounds=int(blend_raw.get("max_refine_rounds", 2)),
        monthly_budget=blend_raw.get("monthly_budget"),
    )
    active = cfg.list_provider_names()
    logger.info("Config: %d providers (%s) loaded", len(active), ", ".join(active))
    return cfg


# ── Singleton ────────────────────────────────────────────────────────────────

_config: BlendConfig | None = None


def get_config() -> BlendConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    global _config
    _config = None
