from __future__ import annotations

from .models import Misi, Prediksi

LEVEL_KEBUTUHAN: dict[str, list[str]] = {
    "Aman": [],
    "Waspada": [],
    "Siaga": ["Logistik", "Dapur Umum", "Kesehatan"],
    "Awas": [
        "Evakuasi",
        "Pencarian & Pertolongan",
        "Logistik",
        "Dapur Umum",
        "Kesehatan",
    ],
}

KEBUTUHAN_KEAHLIAN: dict[str, list[str]] = {
    "Evakuasi": ["Evakuasi", "Perahu", "Fisik"],
    "Pencarian & Pertolongan": ["SAR", "P3K", "Navigasi"],
    "Logistik": ["Logistik", "Mengemudi", "Gudang"],
    "Dapur Umum": ["Memasak", "Kebersihan"],
    "Kesehatan": ["Medis", "P3K", "Psikososial"],
}

LEVEL_KUOTA: dict[str, int] = {"Siaga": 12, "Awas": 24}


def butuh_misi(level: str) -> bool:
    return level in LEVEL_KUOTA


def buat_misi(prediksi: Prediksi) -> Misi:
    level = prediksi.level
    kebutuhan = list(LEVEL_KEBUTUHAN[level])
    keahlian = sorted(
        {skill for kebutuhan_item in kebutuhan for skill in KEBUTUHAN_KEAHLIAN[kebutuhan_item]}
    )
    kuota = LEVEL_KUOTA[level]

    judul = f"Misi {level} Banjir di {prediksi.wilayah}"
    deskripsi = (
        f"Risiko banjir level {level} terdeteksi di {prediksi.wilayah} "
        f"(skor {prediksi.skor_risiko}/100). Dibutuhkan relawan untuk: "
        f"{', '.join(kebutuhan)}."
    )

    return Misi(
        prediksi_id=prediksi.id,
        jenis_bencana=prediksi.jenis_bencana,
        wilayah=prediksi.wilayah,
        judul=judul,
        deskripsi=deskripsi,
        level_risiko=level,
        kebutuhan=kebutuhan,
        keahlian=keahlian,
        kuota=kuota,
        status="dibuka",
    )


def keahlian_cocok(keahlian_relawan: list[str], keahlian_misi: list[str]) -> list[str]:
    relawan = {item.strip().lower() for item in keahlian_relawan if item.strip()}
    misi = {item.strip().lower() for item in keahlian_misi if item.strip()}
    return sorted(relawan & misi)
