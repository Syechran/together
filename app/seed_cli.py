from __future__ import annotations

from .db import SessionLocal, init_db, wait_for_db
from .risk import risk_engine
from .seed import seed_demo


def main() -> None:
    wait_for_db()
    init_db()
    risk_engine.load()
    with SessionLocal() as db:
        jumlah = seed_demo(db, risk_engine)
    if jumlah:
        print(f"Seed demo membuat {jumlah} misi.")
    else:
        print("Database sudah berisi misi; seed dilewati.")


if __name__ == "__main__":
    main()
