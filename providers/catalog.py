"""Model catalog + pricing, loaded from operation_files/MODELS.md.

MODELS.md is the single source of truth. This module reads its machine-readable
``json`` block to:
  * list which providers are *available* (their key env var is set),
  * validate a per-run ``{provider, model}`` choice against the catalog + role,
  * resolve the default model for a role from the env scheme, and
  * price a call (USD) from the per-1M token rates.

Token counts are *estimated* from text length (the stub/offline path returns no
usage); the rate used always comes from the resolved catalog model, so the cost
readout reflects whichever model the run is bound to.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import Settings

_MODELS_FILE = Path(__file__).resolve().parent.parent / "operation_files" / "MODELS.md"
_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

# role -> (provider env attr, role-model env attr) on Settings
_ROLE_ENV = {
    "convo": ("convo_provider", "convo_model"),
    "extract": ("extract_provider", "extract_model"),
}


@lru_cache
def _catalog() -> dict:
    raw = _MODELS_FILE.read_text(encoding="utf-8")
    m = _JSON_FENCE_RE.search(raw)
    if not m:
        raise RuntimeError("MODELS.md: no ```json catalog block found")
    return json.loads(m.group(1))


def providers() -> dict:
    return _catalog()["providers"]


def models() -> dict:
    return _catalog()["models"]


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    model: str
    in_rate: float   # USD per 1M input tokens
    out_rate: float  # USD per 1M output tokens
    roles: tuple[str, ...]


def _info(model_id: str) -> ModelInfo:
    m = models()[model_id]
    return ModelInfo(model_id, m["provider"], m["model"], m["in"], m["out"], tuple(m.get("roles", [])))


def all_for_role(role: str) -> list[ModelInfo]:
    return [_info(mid) for mid, m in models().items() if role in m.get("roles", [])]


def provider_available(provider: str, settings: Settings) -> bool:
    p = providers().get(provider)
    if not p:
        return False
    key = getattr(settings, p["key_env"].lower(), "") or ""
    return bool(key.strip())


def available_for_role(role: str, settings: Settings) -> list[ModelInfo]:
    return [mi for mi in all_for_role(role) if provider_available(mi.provider, settings)]


def find(provider: str, model: str) -> Optional[ModelInfo]:
    for mid, m in models().items():
        if m["provider"] == provider and m["model"] == model:
            return _info(mid)
    return None


def validate_choice(role: str, provider: str, model: str) -> ModelInfo:
    """Return the catalog entry for (provider, model), or raise ValueError if it
    is off-catalog or not allowed for ``role``."""
    mi = find(provider, model)
    if mi is None:
        raise ValueError(f"{provider}/{model} is not in the MODELS.md catalog")
    if role not in mi.roles:
        raise ValueError(f"{provider}/{model} is not a valid '{role}' model")
    return mi


def resolve_default(role: str, settings: Settings) -> Optional[ModelInfo]:
    """Resolve the default model for a role from the env scheme (MODELS.md):
    CONVO_MODEL -> <PROVIDER>_MODEL -> <PROVIDER>_MODEL_DEFAULT, with provider =
    CONVO_PROVIDER. Falls back to the first key-present model for the role."""
    prov_attr, role_model_attr = _ROLE_ENV[role]
    provider = (getattr(settings, prov_attr, "") or "").strip().lower()
    if provider:
        role_model = (getattr(settings, role_model_attr, "") or "").strip()
        prov_model = (getattr(settings, f"{provider}_model", "") or "").strip()
        prov_default = (getattr(settings, f"{provider}_model_default", "") or "").strip()
        model = role_model or prov_model or prov_default
        if model:
            mi = find(provider, model)
            if mi and role in mi.roles:
                return mi
        for cand in available_for_role(role, settings):
            if cand.provider == provider:
                return cand
    avail = available_for_role(role, settings)
    if avail:
        return avail[0]
    pool = all_for_role(role)
    return pool[0] if pool else None


def resolve_role(role: str, choice: Optional[tuple[str, str]], settings: Settings) -> ModelInfo:
    """Resolve the model for a role: validate an explicit choice (raising on
    off-catalog), else fall back to the env default ('ignored-with-default')."""
    if choice:
        return validate_choice(role, choice[0], choice[1])
    mi = resolve_default(role, settings)
    if mi is None:
        raise ValueError(f"no model available for role '{role}' (no provider key set)")
    return mi


# --------------------------------------------------------------------------- #
# Cost metering
# --------------------------------------------------------------------------- #
def estimate_tokens(text: str) -> int:
    """Rough token count (~4 chars/token). Used for the cost readout when the
    provider returns no usage (stub/offline path)."""
    return max(1, math.ceil(len(text or "") / 4))


@dataclass
class RoleMeter:
    role: str
    info: ModelInfo
    in_tokens: int = 0
    out_tokens: int = 0

    def record(self, input_text: str, output_text: str) -> None:
        self.in_tokens += estimate_tokens(input_text)
        self.out_tokens += estimate_tokens(output_text)

    @property
    def usd(self) -> float:
        return round(
            self.in_tokens / 1_000_000 * self.info.in_rate
            + self.out_tokens / 1_000_000 * self.info.out_rate,
            6,
        )

    def block(self) -> dict:
        return {
            "provider": self.info.provider,
            "model": self.info.model,
            "model_id": self.info.id,
            "in_tokens": self.in_tokens,
            "out_tokens": self.out_tokens,
            "usd": self.usd,
        }


def cost_block(convo: RoleMeter, extract: RoleMeter) -> dict:
    return {
        "total_usd": round(convo.usd + extract.usd, 6),
        "convo": convo.block(),
        "extract": extract.block(),
    }
