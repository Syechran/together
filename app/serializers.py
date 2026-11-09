from __future__ import annotations

from typing import Any

from .models import Misi, Partisipasi, Prediksi


def mask_kontak(kontak: str) -> str:
    angka = "".join(character for character in kontak if character.isdigit())
    if len(angka) <= 4:
        return "****"
    if len(angka) <= 6:
        return f"{angka[:2]}****"
    return f"{angka[:4]}{'*' * (len(angka) - 6)}{angka[-2:]}"


def serialize_partisipasi(partisipasi: Partisipasi) -> dict[str, Any]:
    return {
        "id": partisipasi.id,
        "nama": partisipasi.nama,
        "kontak_masked": mask_kontak(partisipasi.kontak),
        "keahlian": list(partisipasi.keahlian or []),
        "status": partisipasi.status,
        "dibuat_pada": partisipasi.dibuat_pada.isoformat(),
    }


def serialize_misi(misi: Misi, detail: bool = False) -> dict[str, Any]:
    terdaftar = [
        partisipasi
        for partisipasi in (misi.partisipasi or [])
        if partisipasi.status == "terdaftar"
    ]
    jumlah = len(terdaftar)
    sisa = max(misi.kuota - jumlah, 0)
    progres = min(round((jumlah / misi.kuota) * 100), 100) if misi.kuota else 0

    data: dict[str, Any] = {
        "id": misi.id,
        "prediksi_id": misi.prediksi_id,
        "jenis_bencana": misi.jenis_bencana,
        "wilayah": misi.wilayah,
        "judul": misi.judul,
        "deskripsi": misi.deskripsi,
        "level_risiko": misi.level_risiko,
        "kebutuhan": list(misi.kebutuhan or []),
        "keahlian": list(misi.keahlian or []),
        "kuota": misi.kuota,
        "relawan_terdaftar": jumlah,
        "sisa_kuota": sisa,
        "progres_pct": progres,
        "status": misi.status,
        "dibuat_pada": misi.dibuat_pada.isoformat(),
    }
    if detail:
        data["partisipasi"] = [
            serialize_partisipasi(item)
            for item in sorted(misi.partisipasi or [], key=lambda row: row.dibuat_pada)
        ]
    return data


def serialize_prediksi(
    prediksi: Prediksi, misi: Misi | None = None
) -> dict[str, Any]:
    if misi is None and prediksi.misi:
        misi = prediksi.misi[0]

    return {
        "id": prediksi.id,
        "jenis_bencana": prediksi.jenis_bencana,
        "wilayah": prediksi.wilayah,
        "curah_hujan_mm": prediksi.curah_hujan_mm,
        "tma_cm": prediksi.tma_cm,
        "drainase_skor": prediksi.drainase_skor,
        "elevasi_m": prediksi.elevasi_m,
        "impervious_pct": prediksi.impervious_pct,
        "skor_risiko": prediksi.skor_risiko,
        "level": prediksi.level,
        "model_versi": prediksi.model_versi,
        "faktor": list(prediksi.faktor or []),
        "rekomendasi": prediksi.rekomendasi,
        "dibuat_pada": prediksi.dibuat_pada.isoformat(),
        "misi": serialize_misi(misi) if misi is not None else None,
    }
