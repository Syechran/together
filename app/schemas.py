from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PrediksiRequest(BaseModel):
    wilayah: str = Field(min_length=3, max_length=120)
    curah_hujan_mm: float = Field(ge=0, le=500, description="Curah hujan 24 jam (mm)")
    tma_cm: float = Field(ge=0, le=1000, description="Tinggi muka air (cm)")
    drainase_skor: float = Field(ge=0, le=10, description="Kualitas drainase 0-10")
    elevasi_m: float = Field(ge=0, le=500, description="Elevasi wilayah (meter)")
    impervious_pct: float = Field(
        ge=0, le=100, description="Persentase permukaan kedap air"
    )

    @field_validator("wilayah")
    @classmethod
    def rapikan_wilayah(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("Nama wilayah terlalu pendek")
        return value


class FaktorOut(BaseModel):
    nama: str
    nilai: str
    keterangan: str


class PartisipasiOut(BaseModel):
    id: int
    nama: str
    kontak_masked: str
    keahlian: list[str]
    status: str
    dibuat_pada: datetime


class MisiOut(BaseModel):
    id: int
    prediksi_id: int
    jenis_bencana: str
    wilayah: str
    judul: str
    deskripsi: str
    level_risiko: str
    kebutuhan: list[str]
    keahlian: list[str]
    kuota: int
    relawan_terdaftar: int
    sisa_kuota: int
    progres_pct: int
    status: str
    dibuat_pada: datetime


class MisiDetail(MisiOut):
    partisipasi: list[PartisipasiOut] = Field(default_factory=list)


class PrediksiOut(BaseModel):
    id: int
    jenis_bencana: str
    wilayah: str
    curah_hujan_mm: float
    tma_cm: float
    drainase_skor: float
    elevasi_m: float
    impervious_pct: float
    skor_risiko: int
    level: str
    model_versi: str
    faktor: list[FaktorOut]
    rekomendasi: str
    dibuat_pada: datetime
    misi: MisiOut | None = None


class GabungRequest(BaseModel):
    nama: str = Field(min_length=2, max_length=120)
    kontak: str = Field(min_length=6, max_length=64)
    keahlian: list[str] = Field(min_length=1, max_length=12)

    @field_validator("nama", "kontak")
    @classmethod
    def rapikan_teks(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Tidak boleh kosong")
        return value

    @field_validator("keahlian")
    @classmethod
    def rapikan_keahlian(cls, values: list[str]) -> list[str]:
        hasil: list[str] = []
        for item in values:
            item = " ".join(item.split())
            if item and item not in hasil:
                hasil.append(item)
        if not hasil:
            raise ValueError("Pilih minimal satu keahlian")
        return hasil


class GabungResponse(BaseModel):
    partisipasi: PartisipasiOut
    misi: MisiDetail


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str]


class StatistikOut(BaseModel):
    total_misi: int
    misi_dibuka: int
    total_relawan: int
    total_prediksi: int
    prediksi_24_jam: int
    level_terakhir: str | None = None


class ErrorOut(BaseModel):
    detail: Any


class BeritaOut(BaseModel):
    id: str
    title: str
    link: str
    source: str
    published: str | None = None
    summary: str
    image: str | None = None
