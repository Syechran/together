from __future__ import annotations

import hashlib
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

FEEDS = [
    ("CNN Indonesia", "https://www.cnnindonesia.com/rss"),
    ("Antara", "https://www.antaranews.com/rss/terkini.xml"),
    (
        "Google News",
        "https://news.google.com/rss/search?q=banjir+Indonesia&hl=id&gl=ID&ceid=ID:id",
    ),
]

FLOOD_TERMS = (
    "banjir",
    "genangan",
    "rob",
    "air pasang",
    "sungai meluap",
    "tanggul jebol",
    "banjir bandang",
)
WATER_CONTEXT = (
    "air",
    "hujan",
    "sungai",
    "parit",
    "drainase",
    "genangan",
    "rob",
    "tanggul",
    "rumah",
    "jalan",
    "desa",
    "kecamatan",
    "warga",
    "korban",
    "mengungsi",
    "pengungsi",
    "tenda",
    "evakuasi",
    "rusak",
    "putus",
    "longsor",
    "sekolah",
    "bpbd",
    "bmkg",
    "bnpb",
    "jakarta",
    "bandung",
    "jawa",
    "sumatera",
    "kalimantan",
    "sulawesi",
    "papua",
    "aceh",
    "medan",
    "surabaya",
    "semarang",
    "yogyakarta",
    "bekasi",
    "depok",
    "tangerang",
    "bogor",
    "malang",
    "palembang",
    "banjarmasin",
    "makassar",
    "manado",
    "ambon",
    "jayapura",
)

EXCLUDE_TERMS = (
    "gaza",
    "palestina",
    "israel",
    "pakistan",
    "india",
    "filipina",
    "thailand",
    "vietnam",
    "tiongkok",
    "china",
    "jepang",
    "malaysia",
    "inggris",
    "amerika",
    "eropa",
    "afrika",
)

USER_AGENT = "Together/1.0 (flood news reader; local demo)"
MAX_ITEMS = 6
MAX_BYTES = 2_000_000


def _bersihkan_teks(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _tanggal(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _gambar(item: ET.Element) -> str | None:
    for node in item.iter():
        tag = node.tag.split("}")[-1].lower()
        if tag not in {"content", "thumbnail", "enclosure"}:
            continue
        url = node.attrib.get("url") or node.attrib.get("href")
        if not url:
            continue
        medium = node.attrib.get("medium", "")
        kind = node.attrib.get("type", "")
        if medium == "image" or "image" in kind or not kind:
            return url

    description = item.findtext("description") or ""
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', description, re.IGNORECASE)
    return html.unescape(match.group(1)) if match else None


def _layak(title: str, description: str) -> bool:
    title_lower = title.lower()
    blob = f"{title_lower} {description.lower()}"
    if not any(term in title_lower for term in FLOOD_TERMS):
        return False
    if any(term in blob for term in EXCLUDE_TERMS) and "indonesia" not in blob:
        return False
    if not any(term in blob for term in WATER_CONTEXT):
        return False
    if "aduan" in title_lower and "air" not in blob and "hujan" not in blob:
        return False
    return True


def _sumber_google(title: str) -> tuple[str, str]:
    match = re.search(r"\s+-\s+([^-]{2,48})$", title)
    if match:
        return title[: match.start()].strip(), match.group(1).strip()
    return title, "Google News"


def _ambil_feed(feed: tuple[str, str]) -> list[dict[str, Any]]:
    source, url = feed
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"})
    with urlopen(request, timeout=7) as response:
        data = response.read(MAX_BYTES)

    root = ET.fromstring(data)
    hasil: list[dict[str, Any]] = []

    for item in root.findall(".//item"):
        title = _bersihkan_teks(item.findtext("title") or "")
        description = _bersihkan_teks(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        if not title or not link or not _layak(title, description):
            continue

        item_source = source
        if source == "Google News":
            title, item_source = _sumber_google(title)

        published = _tanggal(item.findtext("pubDate") or "")
        summary = description[:220].rstrip()
        if len(description) > 220:
            summary += "..."

        hasil.append(
            {
                "id": hashlib.sha1(link.encode("utf-8")).hexdigest()[:12],
                "title": title,
                "link": link,
                "source": item_source,
                "published": published,
                "summary": summary,
                "image": _gambar(item),
            }
        )
    return hasil


def ambil_berita() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(FEEDS)) as pool:
        futures = [pool.submit(_ambil_feed, feed) for feed in FEEDS]
        for future in futures:
            try:
                results.extend(future.result())
            except Exception as exc:
                logger.warning("Gagal mengambil feed berita: %s", exc)

    unik: dict[str, dict[str, Any]] = {}
    for item in results:
        key = re.sub(r"\W+", "", item["title"].lower())[:80]
        if key and key not in unik:
            unik[key] = item

    items = list(unik.values())
    items.sort(key=lambda item: item.get("published") or "", reverse=True)
    return items[:MAX_ITEMS]
