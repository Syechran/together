from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session, selectinload

from . import cache
from .config import settings
from .db import SessionLocal, get_db, init_db, wait_for_db
from .missions import butuh_misi, buat_misi, keahlian_cocok
from .models import Misi, Partisipasi, Prediksi
from .news import ambil_berita
from .risk import risk_engine
from .schemas import (
    BeritaOut,
    GabungRequest,
    GabungResponse,
    HealthResponse,
    MisiDetail,
    MisiOut,
    PrediksiOut,
    PrediksiRequest,
    StatistikOut,
)
from .seed import seed_demo
from .serializers import serialize_misi, serialize_partisipasi, serialize_prediksi

logger = logging.getLogger("together")

mimetypes.add_type("font/woff2", ".woff2")
STATIC_DIR = Path(__file__).resolve().parent / "static"
URUTAN_LEVEL = case(
    (Misi.level_risiko == "Awas", 0),
    (Misi.level_risiko == "Siaga", 1),
    else_=2,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    wait_for_db()
    init_db()
    risk_engine.load()
    if settings.seed_demo:
        with SessionLocal() as db:
            dibuat = seed_demo(db, risk_engine)
            if dibuat:
                logger.info("Seed demo membuat %s misi", dibuat)
    logger.info("Together siap di port 8000")
    yield


app = FastAPI(
    title="Together API",
    description="Dari prediksi risiko banjir menjadi misi relawan yang terkoordinasi.",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(db: Session = Depends(get_db)):
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - jalur gangguan
        logger.warning("Health database gagal: %s", exc)
        checks["database"] = "error"

    try:
        cache.ping()
        checks["cache"] = "ok"
    except Exception as exc:  # pragma: no cover - jalur gangguan
        logger.warning("Health cache gagal: %s", exc)
        checks["cache"] = "error"

    checks["model"] = "ok" if risk_engine.siap else "error"
    sehat = all(nilai == "ok" for nilai in checks.values())
    payload = {
        "status": "ok" if sehat else "degraded",
        "version": settings.app_version,
        "checks": checks,
    }
    if not sehat:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.post(
    "/api/prediksi",
    response_model=PrediksiOut,
    status_code=201,
    tags=["prediksi"],
    summary="Hitung risiko banjir dan buat misi bila melewati ambang",
)
def buat_prediksi(payload: PrediksiRequest, db: Session = Depends(get_db)):
    hasil = risk_engine.predict(payload.model_dump())

    prediksi = Prediksi(
        jenis_bencana="banjir",
        **payload.model_dump(),
        skor_risiko=hasil["skor_risiko"],
        level=hasil["level"],
        model_versi=hasil["model_versi"],
        faktor=hasil["faktor"],
        rekomendasi=hasil["rekomendasi"],
    )
    db.add(prediksi)
    db.flush()

    misi: Misi | None = None
    if butuh_misi(hasil["level"]):
        misi = buat_misi(prediksi)
        db.add(misi)
        db.flush()

    db.commit()
    cache.delete_key(cache.MISI_LIST_KEY)
    return serialize_prediksi(prediksi, misi)


@app.get(
    "/api/prediksi",
    response_model=list[PrediksiOut],
    tags=["prediksi"],
    summary="Riwayat prediksi terbaru",
)
def riwayat_prediksi(
    limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
):
    statement = (
        select(Prediksi)
        .options(selectinload(Prediksi.misi))
        .order_by(Prediksi.dibuat_pada.desc())
        .limit(limit)
    )
    return [serialize_prediksi(item) for item in db.scalars(statement).all()]


@app.get(
    "/api/misi",
    response_model=list[MisiOut],
    tags=["misi"],
    summary="Papan misi relawan",
)
def daftar_misi(
    status: str | None = Query(None, pattern="^(dibuka|penuh|selesai)$"),
    level: str | None = Query(None, pattern="^(Aman|Waspada|Siaga|Awas)$"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    pakai_cache = status is None and level is None and limit == 50
    if pakai_cache:
        tersimpan = cache.get_json(cache.MISI_LIST_KEY)
        if tersimpan is not None:
            return tersimpan

    statement = select(Misi).options(selectinload(Misi.partisipasi))
    if status:
        statement = statement.where(Misi.status == status)
    if level:
        statement = statement.where(Misi.level_risiko == level)
    statement = statement.order_by(URUTAN_LEVEL, Misi.dibuat_pada.desc()).limit(limit)

    data = [serialize_misi(item) for item in db.scalars(statement).all()]
    if pakai_cache:
        cache.set_json(cache.MISI_LIST_KEY, data, settings.cache_ttl_seconds)
    return data


@app.get(
    "/api/misi/{misi_id}",
    response_model=MisiDetail,
    tags=["misi"],
    summary="Detail misi dan relawan terdaftar",
)
def detail_misi(misi_id: int, db: Session = Depends(get_db)):
    misi = db.scalar(
        select(Misi)
        .options(selectinload(Misi.partisipasi))
        .where(Misi.id == misi_id)
    )
    if misi is None:
        raise HTTPException(status_code=404, detail="Misi tidak ditemukan")
    return serialize_misi(misi, detail=True)


@app.post(
    "/api/misi/{misi_id}/gabung",
    response_model=GabungResponse,
    status_code=201,
    tags=["misi"],
    summary="Daftarkan relawan ke misi sesuai keahlian",
)
def gabung_misi(
    misi_id: int, payload: GabungRequest, db: Session = Depends(get_db)
):
    misi = db.scalar(
        select(Misi)
        .options(selectinload(Misi.partisipasi))
        .where(Misi.id == misi_id)
    )
    if misi is None:
        raise HTTPException(status_code=404, detail="Misi tidak ditemukan")

    if misi.status != "dibuka":
        raise HTTPException(
            status_code=409, detail="Misi ini sudah tidak menerima relawan baru"
        )

    terdaftar = sum(
        1 for item in misi.partisipasi if item.status == "terdaftar"
    )
    if terdaftar >= misi.kuota:
        misi.status = "penuh"
        db.commit()
        cache.delete_key(cache.MISI_LIST_KEY)
        raise HTTPException(status_code=409, detail="Kuota relawan sudah penuh")

    cocok = keahlian_cocok(payload.keahlian, list(misi.keahlian or []))
    if not cocok:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Keahlian belum cocok dengan kebutuhan misi",
                "keahlian_dibutuhkan": list(misi.keahlian or []),
            },
        )

    duplikat = db.scalar(
        select(Partisipasi).where(
            Partisipasi.misi_id == misi_id,
            Partisipasi.kontak == payload.kontak,
        )
    )
    if duplikat is not None:
        raise HTTPException(
            status_code=409, detail="Kontak ini sudah terdaftar pada misi tersebut"
        )

    partisipasi = Partisipasi(
        misi_id=misi_id,
        nama=payload.nama,
        kontak=payload.kontak,
        keahlian=payload.keahlian,
    )
    db.add(partisipasi)
    db.flush()

    if terdaftar + 1 >= misi.kuota:
        misi.status = "penuh"

    db.commit()
    cache.delete_key(cache.MISI_LIST_KEY)

    misi = db.scalar(
        select(Misi)
        .options(selectinload(Misi.partisipasi))
        .where(Misi.id == misi_id)
        .execution_options(populate_existing=True)
    )
    return {
        "partisipasi": serialize_partisipasi(partisipasi),
        "misi": serialize_misi(misi, detail=True),
    }




@app.get(
    "/api/berita",
    response_model=list[BeritaOut],
    tags=["berita"],
    summary="Berita banjir Indonesia dari feed publik",
)
def daftar_berita():
    tersimpan = cache.get_json("berita:list")
    if tersimpan is not None:
        return tersimpan

    items = ambil_berita()
    if items:
        cache.set_json("berita:list", items, 900)
    return items


@app.get(
    "/api/statistik",
    response_model=StatistikOut,
    tags=["system"],
    summary="Ringkasan untuk dashboard",
)
def statistik(db: Session = Depends(get_db)):
    batas = datetime.now(timezone.utc) - timedelta(hours=24)
    total_misi = db.scalar(select(func.count(Misi.id))) or 0
    misi_dibuka = (
        db.scalar(select(func.count(Misi.id)).where(Misi.status == "dibuka")) or 0
    )
    total_relawan = (
        db.scalar(
            select(func.count(Partisipasi.id)).where(
                Partisipasi.status == "terdaftar"
            )
        )
        or 0
    )
    total_prediksi = db.scalar(select(func.count(Prediksi.id))) or 0
    prediksi_24_jam = (
        db.scalar(
            select(func.count(Prediksi.id)).where(Prediksi.dibuat_pada >= batas)
        )
        or 0
    )
    level_terakhir = db.scalar(
        select(Prediksi.level).order_by(Prediksi.dibuat_pada.desc()).limit(1)
    )
    return {
        "total_misi": total_misi,
        "misi_dibuka": misi_dibuka,
        "total_relawan": total_relawan,
        "total_prediksi": total_prediksi,
        "prediksi_24_jam": prediksi_24_jam,
        "level_terakhir": level_terakhir,
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
