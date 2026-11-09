from __future__ import annotations

import json
import logging
import os
from threading import Lock
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

FEATURES = [
    "curah_hujan_mm",
    "tma_cm",
    "drainase_skor",
    "elevasi_m",
    "impervious_pct",
]
LABELS = ["Aman", "Waspada", "Siaga", "Awas"]

REKOMENDASI = {
    "Aman": "Tidak perlu misi relawan. Tetap pantau informasi cuaca dan titik rawan.",
    "Waspada": "Siapkan tas siaga dan pantau titik rawan. Misi belum dibuka otomatis.",
    "Siaga": "Misi relawan dibuka. Prioritaskan logistik, dapur umum, dan kesehatan.",
    "Awas": "Misi evakuasi dibuka. Koordinasikan relawan SAR, perahu, dan logistik.",
}


def _angka(value: float) -> str:
    return f"{value:g}"


def _susun_faktor(payload: dict[str, float]) -> list[dict[str, str]]:
    faktor: list[dict[str, str]] = []

    hujan = payload["curah_hujan_mm"]
    if hujan >= 200:
        faktor.append(
            {"nama": "Curah hujan", "nilai": _angka(hujan), "keterangan": "sangat tinggi"}
        )
    elif hujan >= 100:
        faktor.append(
            {"nama": "Curah hujan", "nilai": _angka(hujan), "keterangan": "tinggi"}
        )

    tma = payload["tma_cm"]
    if tma >= 350:
        faktor.append(
            {"nama": "Tinggi muka air", "nilai": _angka(tma), "keterangan": "kritis"}
        )
    elif tma >= 250:
        faktor.append(
            {"nama": "Tinggi muka air", "nilai": _angka(tma), "keterangan": "tinggi"}
        )

    drainase = payload["drainase_skor"]
    if drainase <= 3:
        faktor.append(
            {"nama": "Drainase", "nilai": _angka(drainase), "keterangan": "buruk"}
        )
    elif drainase <= 6:
        faktor.append(
            {"nama": "Drainase", "nilai": _angka(drainase), "keterangan": "terbatas"}
        )

    elevasi = payload["elevasi_m"]
    if elevasi <= 10:
        faktor.append(
            {"nama": "Elevasi", "nilai": _angka(elevasi), "keterangan": "sangat rendah"}
        )
    elif elevasi <= 20:
        faktor.append(
            {"nama": "Elevasi", "nilai": _angka(elevasi), "keterangan": "rendah"}
        )

    impervious = payload["impervious_pct"]
    if impervious >= 80:
        faktor.append(
            {
                "nama": "Permukaan kedap air",
                "nilai": _angka(impervious),
                "keterangan": "sangat luas",
            }
        )
    elif impervious >= 60:
        faktor.append(
            {
                "nama": "Permukaan kedap air",
                "nilai": _angka(impervious),
                "keterangan": "luas",
            }
        )

    if not faktor:
        faktor.append(
            {
                "nama": "Parameter wilayah",
                "nilai": "normal",
                "keterangan": "tidak ada faktor dominan",
            }
        )
    return faktor[:5]


class RiskEngine:
    def __init__(self) -> None:
        self.model: dict[str, Any] | None = None
        self.meta: dict[str, Any] = {}
        self._lock = Lock()

    @property
    def siap(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        with self._lock:
            if self.model is not None:
                return
            if not os.path.exists(settings.model_path):
                raise RuntimeError(
                    f"Model tidak ditemukan di {settings.model_path}. "
                    "Jalankan ml/train_model.py atau build lewat Docker."
                )
            with open(settings.model_path, encoding="utf-8") as file:
                self.model = json.load(file)

            meta_path = os.path.splitext(settings.model_path)[0] + "_meta.json"
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as file:
                    self.meta = json.load(file)

            logger.info(
                "Model JSON dimuat (versi %s, %s pohon, akurasi uji %s)",
                self.meta.get("version", self.model.get("version", "unknown")),
                self.model.get("n_trees", len(self.model.get("trees", []))),
                self.meta.get("accuracy", "unknown"),
            )

    def _inferensi(self, baris: list[float]) -> list[float]:
        if self.model is None:
            raise RuntimeError("Model risiko belum dimuat")

        pohon_pohon = self.model["trees"]
        total = [0.0] * len(LABELS)

        for pohon in pohon_pohon:
            node = 0
            while pohon["left"][node] != -1:
                fitur = pohon["feature"][node]
                if baris[fitur] <= pohon["threshold"][node]:
                    node = pohon["left"][node]
                else:
                    node = pohon["right"][node]
            for indeks, nilai in enumerate(pohon["proba"][node]):
                total[indeks] += nilai

        jumlah = len(pohon_pohon)
        return [nilai / jumlah for nilai in total]

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        nilai_fitur = {name: float(payload[name]) for name in FEATURES}
        baris = [nilai_fitur[name] for name in FEATURES]
        probabilitas = self._inferensi(baris)

        indeks = max(range(len(probabilitas)), key=probabilitas.__getitem__)
        skor = int(
            round(
                sum(nilai * posisi for posisi, nilai in enumerate(probabilitas))
                / (len(LABELS) - 1)
                * 100
            )
        )
        level = LABELS[indeks]

        return {
            "level": level,
            "skor_risiko": skor,
            "probabilitas": {
                label: round(float(prob), 4)
                for label, prob in zip(LABELS, probabilitas)
            },
            "faktor": _susun_faktor(nilai_fitur),
            "rekomendasi": REKOMENDASI[level],
            "model_versi": str(
                self.meta.get("version", self.model.get("version", "1.0.0"))
            ),
        }


risk_engine = RiskEngine()
