"""
Environment-driven settings. Copy .env.example to .env and adjust.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _f(key: str, default: float) -> float:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    return float(v)


def _i(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    return int(v)


@dataclass(frozen=True)
class Settings:
    """Opinionated defaults: 12-month horizon, 6-month emergency-fund target, clear risk bands."""

    secret_key: str
    database_url: str
    access_token_expire_minutes: int

    default_horizon_months: int
    safety_target_months: float
    default_min_balance: float

    # Risk classification (aligned with common personal-finance guidance)
    ef_months_high: float
    ef_months_caution: float
    dti_high: float
    dti_caution: float
    runway_months_high: int
    runway_months_caution: int

    # Advice / copy
    ef_months_recommended_min: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        secret_key=os.getenv("MM_SECRET_KEY", "money-mirror-dev-secret-change-in-production"),
        database_url=os.getenv("MM_DATABASE_URL", "sqlite:///./money_mirror.db"),
        access_token_expire_minutes=_i("MM_ACCESS_TOKEN_MINUTES", 60 * 24 * 7),
        default_horizon_months=_i("MM_DEFAULT_HORIZON_MONTHS", 12),
        safety_target_months=_f("MM_SAFETY_TARGET_MONTHS", 6.0),
        default_min_balance=_f("MM_DEFAULT_MIN_BALANCE", 10_000.0),
        ef_months_high=_f("MM_EF_MONTHS_HIGH", 3.0),
        ef_months_caution=_f("MM_EF_MONTHS_CAUTION", 6.0),
        dti_high=_f("MM_DTI_HIGH", 0.50),
        dti_caution=_f("MM_DTI_CAUTION", 0.40),
        runway_months_high=_i("MM_RUNWAY_MONTHS_HIGH", 2),
        runway_months_caution=_i("MM_RUNWAY_MONTHS_CAUTION", 4),
        ef_months_recommended_min=_f("MM_EF_RECOMMENDED_MIN", 3.0),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()
