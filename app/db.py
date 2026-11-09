from __future__ import annotations

import logging
import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(attempts: int = 30, delay_seconds: float = 2.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database siap pada percobaan %s", attempt)
            return
        except Exception as exc:  # pragma: no cover - hanya jalur startup
            if attempt == attempts:
                raise RuntimeError("Database tidak dapat dihubungi") from exc
            logger.warning(
                "Database belum siap (%s/%s): %s", attempt, attempts, exc.__class__.__name__
            )
            time.sleep(delay_seconds)


def init_db() -> None:
    from . import models  # noqa: F401  (registrasi metadata)

    Base.metadata.create_all(bind=engine)
