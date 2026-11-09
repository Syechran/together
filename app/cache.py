from __future__ import annotations

import json
import logging
from typing import Any

import redis

from .config import settings

logger = logging.getLogger(__name__)

_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

MISI_LIST_KEY = "misi:list"


def ping() -> bool:
    return bool(_client.ping())


def get_json(key: str) -> Any | None:
    try:
        raw = _client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:  # cache tidak boleh menjatuhkan aplikasi
        logger.warning("Gagal membaca cache %s: %s", key, exc)
        return None


def set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    try:
        _client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    except Exception as exc:
        logger.warning("Gagal menulis cache %s: %s", key, exc)


def delete_key(key: str) -> None:
    try:
        _client.delete(key)
    except Exception as exc:
        logger.warning("Gagal menghapus cache %s: %s", key, exc)
