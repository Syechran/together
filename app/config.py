from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Together"
    app_version: str = "1.0.0"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://together:ubah_password_ini@localhost:5432/together",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    model_path: str = os.getenv("MODEL_PATH", "model/model.json")
    seed_demo: bool = _bool_env("SEED_DEMO", False)
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "10"))


settings = Settings()
