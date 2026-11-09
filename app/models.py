from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Prediksi(Base):
    __tablename__ = "prediksi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jenis_bencana: Mapped[str] = mapped_column(
        String(32), default="banjir", index=True
    )
    wilayah: Mapped[str] = mapped_column(String(120), index=True)

    curah_hujan_mm: Mapped[float] = mapped_column(Float)
    tma_cm: Mapped[float] = mapped_column(Float)
    drainase_skor: Mapped[float] = mapped_column(Float)
    elevasi_m: Mapped[float] = mapped_column(Float)
    impervious_pct: Mapped[float] = mapped_column(Float)

    skor_risiko: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(16), index=True)
    model_versi: Mapped[str] = mapped_column(String(32))
    faktor: Mapped[list] = mapped_column(JSON, default=list)
    rekomendasi: Mapped[str] = mapped_column(Text, default="")
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    misi: Mapped[list["Misi"]] = relationship(
        back_populates="prediksi",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Misi(Base):
    __tablename__ = "misi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediksi_id: Mapped[int] = mapped_column(
        ForeignKey("prediksi.id", ondelete="CASCADE"), index=True
    )
    jenis_bencana: Mapped[str] = mapped_column(String(32), default="banjir")
    wilayah: Mapped[str] = mapped_column(String(120), index=True)
    judul: Mapped[str] = mapped_column(String(180))
    deskripsi: Mapped[str] = mapped_column(Text)
    level_risiko: Mapped[str] = mapped_column(String(16), index=True)
    kebutuhan: Mapped[list] = mapped_column(JSON, default=list)
    keahlian: Mapped[list] = mapped_column(JSON, default=list)
    kuota: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="dibuka", index=True)
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    prediksi: Mapped[Prediksi] = relationship(back_populates="misi")
    partisipasi: Mapped[list["Partisipasi"]] = relationship(
        back_populates="misi",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Partisipasi(Base):
    __tablename__ = "partisipasi"
    __table_args__ = (
        UniqueConstraint("misi_id", "kontak", name="uq_partisipasi_misi_kontak"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    misi_id: Mapped[int] = mapped_column(
        ForeignKey("misi.id", ondelete="CASCADE"), index=True
    )
    nama: Mapped[str] = mapped_column(String(120))
    kontak: Mapped[str] = mapped_column(String(64))
    keahlian: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="terdaftar")
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    misi: Mapped[Misi] = relationship(back_populates="partisipasi")
