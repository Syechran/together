from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .missions import butuh_misi, buat_misi, keahlian_cocok
from .models import Misi, Partisipasi, Prediksi
from .risk import RiskEngine

logger = logging.getLogger(__name__)

SCENARIOS: list[dict[str, Any]] = [
    {
        "wilayah": "Bojongloa Kaler",
        "curah_hujan_mm": 235,
        "tma_cm": 365,
        "drainase_skor": 2,
        "elevasi_m": 6,
        "impervious_pct": 88,
        "relawan": [
            {"nama": "Rina Dummy", "kontak": "0812-DUMMY-001", "keahlian": ["Logistik", "Mengemudi"]},
            {"nama": "Budi Dummy", "kontak": "0812-DUMMY-002", "keahlian": ["Medis", "P3K"]},
            {"nama": "Sari Dummy", "kontak": "0812-DUMMY-003", "keahlian": ["Memasak", "Kebersihan"]},
        ],
    },
    {
        "wilayah": "Buahbatu",
        "curah_hujan_mm": 160,
        "tma_cm": 280,
        "drainase_skor": 4,
        "elevasi_m": 14,
        "impervious_pct": 72,
        "relawan": [
            {"nama": "Andi Dummy", "kontak": "0812-DUMMY-004", "keahlian": ["Logistik", "Gudang"]},
            {"nama": "Dewi Dummy", "kontak": "0812-DUMMY-005", "keahlian": ["P3K", "Psikososial"]},
        ],
    },
    {
        "wilayah": "Coblong",
        "curah_hujan_mm": 45,
        "tma_cm": 130,
        "drainase_skor": 8,
        "elevasi_m": 32,
        "impervious_pct": 45,
        "relawan": [],
    },
]


def seed_demo(db: Session, engine: RiskEngine) -> int:
    total_misi = db.scalar(select(func.count(Misi.id))) or 0
    if total_misi > 0:
        return 0

    jumlah_misi = 0
    for skenario in SCENARIOS:
        relawan = skenario.get("relawan", [])
        payload = {
            "curah_hujan_mm": skenario["curah_hujan_mm"],
            "tma_cm": skenario["tma_cm"],
            "drainase_skor": skenario["drainase_skor"],
            "elevasi_m": skenario["elevasi_m"],
            "impervious_pct": skenario["impervious_pct"],
        }
        hasil = engine.predict(payload)
        prediksi = Prediksi(
            jenis_bencana="banjir",
            wilayah=skenario["wilayah"],
            model_versi=hasil["model_versi"],
            skor_risiko=hasil["skor_risiko"],
            level=hasil["level"],
            faktor=hasil["faktor"],
            rekomendasi=hasil["rekomendasi"],
            **payload,
        )
        db.add(prediksi)
        db.flush()

        if not butuh_misi(hasil["level"]):
            continue

        misi = buat_misi(prediksi)
        db.add(misi)
        db.flush()
        jumlah_misi += 1

        for data_relawan in relawan:
            if not keahlian_cocok(data_relawan["keahlian"], misi.keahlian):
                continue
            db.add(
                Partisipasi(
                    misi_id=misi.id,
                    nama=data_relawan["nama"],
                    kontak=data_relawan["kontak"],
                    keahlian=data_relawan["keahlian"],
                )
            )

    db.commit()
    logger.info("Seed demo selesai: %s misi dibuat", jumlah_misi)
    return jumlah_misi
