"""İçerik Arşivi (Faz 6.2) demo seed — idempotent.

Processor çıktısını taklit eden gerçekçi `raw_items` + cross-schema
`processed_items` + `digests`/`digest_sections` (bülten kullanımı) +
`content_chunks` (RAG parça sayısı) kayıtları üretir. Yalnızca dev/test.

Çalıştırma:
    .venv/bin/python scripts/seed_content_archive.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.core.config import Settings, get_settings  # noqa: E402
from packages.shared.enums import (  # noqa: E402
    DigestStatus,
    DigestType,
    RawItemStatus,
)
from packages.shared.env_loader import load_dotenv_file  # noqa: E402
from packages.shared.models.content_chunk import (  # noqa: E402
    EMBEDDING_DIMENSION,
    ContentChunk,
)
from packages.shared.models.digest import Digest  # noqa: E402
from packages.shared.models.digest_section import DigestSection  # noqa: E402
from packages.shared.models.processed_item import (  # noqa: E402
    PROCESSED_ITEM_MODELS,
    ProcessedItem,
)
from packages.shared.models.raw_item import RawItem  # noqa: E402

logger = logging.getLogger("ygip.seed_archive")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


# Mevcut fixtures/sources.json kaynak id'leri (seed_sources ile uyumlu).
SRC_DUNYA = "b0000001-0000-4000-8000-000000000001"
SRC_BLOOMBERG = "b0000002-0000-4000-8000-000000000002"
SRC_PERAKENDE = "b0000004-0000-4000-8000-000000000004"
SRC_FOODNAV = "b0000007-0000-4000-8000-000000000007"
SRC_EKONOMIM = "b0000006-0000-4000-8000-000000000006"
SRC_MCKINSEY = "b0000022-0000-4000-8000-000000000022"
SRC_RESMI = "b0000027-0000-4000-8000-000000000027"
SRC_ECONOMIST = "b0000028-0000-4000-8000-000000000028"
SRC_NIELSEN = "b0000035-0000-4000-8000-000000000035"

# Kaynak id → makale URL domaini (demo link üretimi için).
SOURCE_DOMAIN: dict[str, str] = {
    SRC_DUNYA: "https://www.dunya.com/haber",
    SRC_BLOOMBERG: "https://www.bloomberght.com/haber",
    SRC_PERAKENDE: "https://www.perakende.org/haber",
    SRC_FOODNAV: "https://www.foodnavigator.com/Article",
    SRC_EKONOMIM: "https://www.ekonomim.com/haber",
    SRC_MCKINSEY: "https://www.mckinsey.com/insights",
    SRC_RESMI: "https://www.resmigazete.gov.tr/eskiler",
    SRC_ECONOMIST: "https://www.economist.com/article",
    SRC_NIELSEN: "https://nielseniq.com/global/insights",
}


def _article_url(item: dict[str, Any]) -> str:
    base = SOURCE_DOMAIN.get(item["source_id"], "https://example.com/haber")
    return f"{base}/{item['idx']}-demo-arsiv"


# Her kayıt: (idx, schema, source_id, content_category, title, topics, score,
#             published_at, processed_at, lang, summary, clean_content)
ITEMS: list[dict[str, Any]] = [
    {
        "idx": 1,
        "schema": "news",
        "source_id": SRC_BLOOMBERG,
        "content_category": "macro",
        "title": "TCMB politika faizini sabit tuttu, piyasalar tepki verdi",
        "topics": ["tcmb", "faiz", "para politikası"],
        "score": 0.91,
        "published_at": "2026-06-12T09:30:00",
        "processed_at": "2026-06-12T09:34:00",
        "summary": "TCMB politika faizini %42,5 seviyesinde sabit bıraktı.",
        "clean_content": (
            "Türkiye Cumhuriyet Merkez Bankası (TCMB) Para Politikası Kurulu, "
            "politika faizini %42,5 seviyesinde sabit tuttu. Karar piyasa "
            "beklentileriyle uyumlu olsa da, kurul metnindeki sıkı duruş "
            "vurgusu döviz ve tahvil piyasalarında dalgalanmaya yol açtı. "
            "Analistler, yıl sonu enflasyon patikasının kritik olduğunu belirtiyor."
        ),
    },
    {
        "idx": 2,
        "schema": "news",
        "source_id": SRC_EKONOMIM,
        "content_category": "macro",
        "title": "Mayıs enflasyonu beklentilerin altında kaldı",
        "topics": ["enflasyon", "tüfe", "makroekonomi"],
        "score": 0.84,
        "published_at": "2026-06-03T10:00:00",
        "processed_at": "2026-06-03T10:05:00",
        "summary": "Aylık TÜFE %2,1 ile beklentilerin altında gerçekleşti.",
        "clean_content": (
            "Türkiye İstatistik Kurumu verilerine göre mayıs ayında tüketici "
            "fiyatları aylık %2,1 arttı; bu rakam %2,6 olan piyasa beklentisinin "
            "altında kaldı. Yıllık enflasyon ise gerileme eğilimini sürdürdü. "
            "Veri sonrası dezenflasyon sürecine ilişkin iyimserlik arttı."
        ),
    },
    {
        "idx": 3,
        "schema": "news",
        "source_id": SRC_DUNYA,
        "content_category": "finance",
        "title": "Borsa İstanbul haftayı rekorla kapattı",
        "topics": ["borsa", "bist100", "hisse"],
        "score": 0.72,
        "published_at": "2026-06-06T17:45:00",
        "processed_at": "2026-06-06T17:50:00",
        "summary": "BIST 100 endeksi tüm zamanların en yüksek kapanışını yaptı.",
        "clean_content": (
            "Borsa İstanbul'da BIST 100 endeksi haftanın son işlem gününde "
            "%1,8 yükselerek rekor seviyeden kapandı. Bankacılık ve holding "
            "hisselerindeki güçlü alımlar endeksi yukarı taşıdı. Yabancı "
            "yatırımcı ilgisinin arttığı gözlendi."
        ),
    },
    {
        "idx": 4,
        "schema": "news",
        "source_id": SRC_RESMI,
        "content_category": "regulatory",
        "title": "Resmi Gazete: Gıda etiketleme yönetmeliğinde değişiklik",
        "topics": ["regülasyon", "gıda", "etiketleme"],
        "score": 0.68,
        "published_at": "2026-06-09T08:00:00",
        "processed_at": "2026-06-09T08:06:00",
        "summary": "Ambalajlı gıdalarda besin değeri etiketlemesi zorunlu hale geldi.",
        "clean_content": (
            "Resmi Gazete'de yayımlanan yönetmelik değişikliğiyle ambalajlı "
            "gıda ürünlerinde besin değeri ve şeker içeriği etiketlemesi "
            "kademeli olarak zorunlu hale getirildi. Üreticilere uyum için "
            "12 aylık geçiş süresi tanındı."
        ),
    },
    {
        "idx": 5,
        "schema": "news",
        "source_id": SRC_MCKINSEY,
        "content_category": "strategy",
        "title": "McKinsey: 2026 küresel büyüme görünümü güçleniyor",
        "topics": ["strateji", "büyüme", "küresel ekonomi"],
        "score": 0.79,
        "published_at": "2026-06-10T12:00:00",
        "processed_at": "2026-06-10T12:07:00",
        "summary": "Rapor, gelişmekte olan pazarlarda toparlanmaya işaret ediyor.",
        "clean_content": (
            "McKinsey Global Institute raporuna göre 2026 yılında küresel "
            "büyüme görünümü, düşen enflasyon ve gevşeyen finansal koşullar "
            "sayesinde güçleniyor. Rapor özellikle gelişmekte olan pazarlarda "
            "tüketim kaynaklı toparlanmaya dikkat çekiyor."
        ),
    },
    {
        "idx": 6,
        "schema": "market",
        "source_id": SRC_BLOOMBERG,
        "content_category": "finance",
        "title": "Kakao vadeli işlemleri yeni zirve gördü",
        "topics": ["kakao", "emtia", "fiyat"],
        "score": 0.88,
        "published_at": "2026-06-11T14:20:00",
        "processed_at": "2026-06-11T14:25:00",
        "summary": "Arz endişeleri kakao fiyatlarını rekor seviyeye taşıdı.",
        "clean_content": (
            "Batı Afrika'daki olumsuz hava koşulları ve arz endişeleri, kakao "
            "vadeli işlem fiyatlarını ton başına yeni rekor seviyeye taşıdı. "
            "Çikolata üreticileri maliyet baskısı altında; fiyat artışlarının "
            "tüketiciye yansıması bekleniyor."
        ),
    },
    {
        "idx": 7,
        "schema": "market",
        "source_id": SRC_BLOOMBERG,
        "content_category": "finance",
        "title": "Dolar/TL haftayı yatay seyirle tamamladı",
        "topics": ["döviz", "dolar", "kur"],
        "score": 0.61,
        "published_at": "2026-06-06T18:00:00",
        "processed_at": "2026-06-06T18:04:00",
        "summary": "Kur, dar bir bantta hareket ederek haftayı yatay kapattı.",
        "clean_content": (
            "Dolar/TL paritesi hafta boyunca dar bir bantta hareket ederek "
            "yatay bir seyir izledi. TCMB'nin sıkı duruşu ve güçlü rezerv "
            "görünümü kuru baskıladı. Piyasa, yeni haftada enflasyon verisine "
            "odaklandı."
        ),
    },
    {
        "idx": 8,
        "schema": "fmcg",
        "source_id": SRC_PERAKENDE,
        "content_category": "fmcg",
        "title": "Ülker yeni üretim hattı yatırımını duyurdu",
        "topics": ["ülker", "yatırım", "üretim"],
        "score": 0.86,
        "published_at": "2026-06-08T11:15:00",
        "processed_at": "2026-06-08T11:20:00",
        "summary": "Şirket, ihracat kapasitesini artıracak yeni hattı açıkladı.",
        "clean_content": (
            "Ülker, atıştırmalık kategorisinde ihracat kapasitesini artırmak "
            "amacıyla yeni bir üretim hattı yatırımını duyurdu. Yatırımın "
            "bölgesel pazarlarda büyümeyi destekleyeceği belirtildi. Şirket "
            "sürdürülebilir ambalaj hedeflerine de vurgu yaptı."
        ),
    },
    {
        "idx": 9,
        "schema": "fmcg",
        "source_id": SRC_NIELSEN,
        "content_category": "fmcg",
        "title": "NielsenIQ: FMCG fiyat artışları yavaşlıyor",
        "topics": ["fmcg", "fiyatlama", "tüketim"],
        "score": 0.77,
        "published_at": "2026-06-10T09:00:00",
        "processed_at": "2026-06-10T09:05:00",
        "summary": "Raporda hacim büyümesinin yeniden pozitife döndüğü belirtiliyor.",
        "clean_content": (
            "NielsenIQ'nun son raporuna göre hızlı tüketim ürünlerinde fiyat "
            "artış hızı yavaşlıyor ve hacim büyümesi yeniden pozitif bölgeye "
            "geçiyor. Tüketiciler indirimli ürün ve özel markalara yöneliyor. "
            "Perakendeciler promosyon stratejilerini yeniden kurguluyor."
        ),
    },
    {
        "idx": 10,
        "schema": "fmcg",
        "source_id": SRC_FOODNAV,
        "content_category": "fmcg",
        "lang": "en",
        "title": "European snack demand rebounds in early summer",
        "topics": ["snacks", "europe", "demand"],
        "score": 0.58,
        "published_at": "2026-06-05T13:30:00",
        "processed_at": "2026-06-05T13:36:00",
        "summary": "Snacking category shows renewed growth across the EU market.",
        "clean_content": (
            "Snacking demand across European markets rebounded in early summer, "
            "driven by premium and better-for-you products. Manufacturers are "
            "reformulating to reduce sugar content while protecting taste. "
            "Private label continues to gain share in the category."
        ),
    },
    {
        "idx": 11,
        "schema": "geo",
        "source_id": SRC_ECONOMIST,
        "content_category": "geopolitical",
        "title": "Kızıldeniz'de lojistik gerilim ticaret rotalarını etkiliyor",
        "topics": ["jeopolitik", "lojistik", "kızıldeniz"],
        "score": 0.74,
        "published_at": "2026-06-07T07:00:00",
        "processed_at": "2026-06-07T07:08:00",
        "summary": "Gerilim nedeniyle konteyner gemileri rota değiştiriyor.",
        "clean_content": (
            "Kızıldeniz'deki güvenlik gerilimi nedeniyle büyük konteyner "
            "taşıyıcıları rotalarını Ümit Burnu üzerinden değiştirmeye devam "
            "ediyor. Bu durum navlun maliyetlerini ve teslim sürelerini "
            "artırıyor; küresel tedarik zincirlerinde baskı yaratıyor."
        ),
    },
    {
        "idx": 12,
        "schema": "transport",
        "source_id": SRC_ECONOMIST,
        "content_category": "geopolitical",
        "title": "Süveyş Kanalı trafiği kademeli olarak normale dönüyor",
        "topics": ["süveyş", "denizyolu", "tedarik zinciri"],
        "score": 0.66,
        "published_at": "2026-06-09T15:10:00",
        "processed_at": "2026-06-09T15:15:00",
        "summary": "Kanal geçişlerinde toparlanma sinyalleri görülüyor.",
        "clean_content": (
            "Süveyş Kanalı'ndan geçen gemi sayısında kademeli bir toparlanma "
            "gözleniyor. Otoriteler, geçiş güvenliğine ilişkin önlemlerin "
            "artırıldığını açıkladı. Lojistik şirketleri yine de alternatif "
            "rota planlamasını sürdürüyor."
        ),
    },
]


# Bülten kullanımı: digest + sections (source_references içindeki processed_item idx).
def _pid(idx: int) -> str:
    return f"c2000000-0000-4000-8000-{idx:012d}"


def _ref(idx: int) -> dict[str, Any]:
    item = next(it for it in ITEMS if it["idx"] == idx)
    return {
        "processed_item_id": _pid(idx),
        "title": item["title"],
        "url": None,
    }


DIGESTS: list[dict[str, Any]] = [
    {
        "id": "c3000000-0000-4000-8000-000000000001",
        "digest_type": DigestType.STRATEGY_WEEKLY,
        "title": "Strateji Haftalık — 9–15 Haziran 2026",
        "period_start": date(2026, 6, 9),
        "period_end": date(2026, 6, 15),
        "sections": [
            {
                "id": "c4000000-0000-4000-8000-000000000001",
                "order": 1,
                "title": "Makroekonomik Gelişmeler",
                "summary": (
                    "TCMB'nin faiz kararı ve enflasyon verileri haftanın "
                    "makroekonomik gündemini belirledi."
                ),
                "impact": "Yıldız Holding finansman maliyetleri açısından izlenmeli.",
                "refs": [1, 2],
            },
            {
                "id": "c4000000-0000-4000-8000-000000000002",
                "order": 2,
                "title": "Stratejik Görünüm",
                "summary": "Küresel büyüme beklentileri yukarı yönlü revize edildi.",
                "impact": "İhracat pazarlarında fırsat penceresi.",
                "refs": [5],
            },
        ],
    },
    {
        "id": "c3000000-0000-4000-8000-000000000002",
        "digest_type": DigestType.FMCG_WEEKLY,
        "title": "FMCG Haftalık — 9–15 Haziran 2026",
        "period_start": date(2026, 6, 9),
        "period_end": date(2026, 6, 15),
        "sections": [
            {
                "id": "c4000000-0000-4000-8000-000000000003",
                "order": 1,
                "title": "Sektör Hareketleri",
                "summary": (
                    "Ülker'in yatırım açıklaması ve NielsenIQ verileri sektörde "
                    "toparlanmaya işaret ediyor."
                ),
                "impact": "Kategori büyümesi hacim bazlı geri dönüyor.",
                "refs": [8, 9],
            },
        ],
    },
    {
        "id": "c3000000-0000-4000-8000-000000000003",
        "digest_type": DigestType.TURKISH_MEDIA_WEEKLY,
        "title": "Türk Medyası Haftalık — 2–8 Haziran 2026",
        "period_start": date(2026, 6, 2),
        "period_end": date(2026, 6, 8),
        "sections": [
            {
                "id": "c4000000-0000-4000-8000-000000000004",
                "order": 1,
                "title": "Piyasa ve Finans",
                "summary": "Borsa İstanbul rekor kapanışıyla haftanın öne çıkanı oldu.",
                "impact": None,
                "refs": [3],
            },
        ],
    },
]


async def _seed_raw_and_processed(db: AsyncSession) -> tuple[int, int]:
    raw_created = 0
    proc_created = 0
    for item in ITEMS:
        idx = item["idx"]
        raw_id = uuid.UUID(f"c1000000-0000-4000-8000-{idx:012d}")
        proc_id = uuid.UUID(_pid(idx))
        model = PROCESSED_ITEM_MODELS[item["schema"]]
        url = _article_url(item)

        existing_raw = await db.get(RawItem, raw_id)
        if existing_raw is None:
            db.add(
                RawItem(
                    id=raw_id,
                    source_id=uuid.UUID(item["source_id"]),
                    external_id=url,
                    content_hash=f"seedhash{idx:056d}",
                    title=item["title"],
                    raw_content=item["clean_content"],
                    raw_metadata={"url": url},
                    fetched_at=_dt(item["processed_at"]),
                    status=RawItemStatus.PROCESSED,
                )
            )
            raw_created += 1
        elif existing_raw.raw_metadata.get("url") != url:
            # Idempotent güncelleme — eski seed kayıtlarına URL ekle.
            merged = dict(existing_raw.raw_metadata)
            merged["url"] = url
            existing_raw.raw_metadata = merged
            flag_modified(existing_raw, "raw_metadata")

        if await db.get(model, proc_id) is None:
            proc: ProcessedItem = model(
                id=proc_id,
                raw_item_id=raw_id,
                source_id=uuid.UUID(item["source_id"]),
                title=item["title"],
                clean_content=item["clean_content"],
                summary=item["summary"],
                language=item.get("lang", "tr"),
                relevance_score=item["score"],
                topics=item["topics"],
                entities=[],
                published_at=_dt(item["published_at"]),
                processed_at=_dt(item["processed_at"]),
                schema_category=item["schema"],
                content_category=item["content_category"],
            )
            db.add(proc)
            proc_created += 1
    await db.flush()
    return raw_created, proc_created


async def _seed_chunks(db: AsyncSession) -> int:
    """İlk birkaç içerik için RAG parçaları (chunk_count > 0 görünmesi için)."""
    created = 0
    zero_vec = [0.0] * EMBEDDING_DIMENSION
    chunk_plan = {1: 3, 5: 2, 8: 2, 9: 2}  # processed_item idx -> chunk sayısı
    for idx, count in chunk_plan.items():
        proc_id = uuid.UUID(_pid(idx))
        for chunk_index in range(count):
            chunk_id = uuid.UUID(
                f"c5000000-0000-4000-{idx:04d}-{chunk_index:012d}"
            )
            if await db.get(ContentChunk, chunk_id) is not None:
                continue
            db.add(
                ContentChunk(
                    id=chunk_id,
                    processed_item_id=proc_id,
                    chunk_index=chunk_index,
                    chunk_text=f"Demo RAG parçası {chunk_index} (içerik {idx}).",
                    token_count=64,
                    embedding=zero_vec,
                )
            )
            created += 1
    await db.flush()
    return created


async def _seed_digests(db: AsyncSession) -> tuple[int, int]:
    digest_created = 0
    section_created = 0
    for d in DIGESTS:
        digest_id = uuid.UUID(d["id"])
        if await db.get(Digest, digest_id) is None:
            db.add(
                Digest(
                    id=digest_id,
                    digest_type=d["digest_type"],
                    title=d["title"],
                    status=DigestStatus.READY,
                    period_start=d["period_start"],
                    period_end=d["period_end"],
                    total_sources_used=sum(len(s["refs"]) for s in d["sections"]),
                    generation_metadata={},
                    completed_at=_dt("2026-06-15T06:00:00"),
                )
            )
            digest_created += 1

        for section in d["sections"]:
            section_id = uuid.UUID(section["id"])
            if await db.get(DigestSection, section_id) is not None:
                continue
            db.add(
                DigestSection(
                    id=section_id,
                    digest_id=digest_id,
                    section_order=section["order"],
                    section_title=section["title"],
                    ai_summary=section["summary"],
                    impact_note=section["impact"],
                    source_references=[_ref(i) for i in section["refs"]],
                )
            )
            section_created += 1
    await db.flush()
    return digest_created, section_created


async def run(db: AsyncSession) -> dict[str, int]:
    raw_created, proc_created = await _seed_raw_and_processed(db)
    chunk_created = await _seed_chunks(db)
    digest_created, section_created = await _seed_digests(db)
    return {
        "raw_items": raw_created,
        "processed_items": proc_created,
        "content_chunks": chunk_created,
        "digests": digest_created,
        "digest_sections": section_created,
    }


def _assert_dev(settings: Settings) -> None:
    if settings.ENVIRONMENT == "production":
        msg = "Seed script yalnızca dev/test ortamında çalıştırılabilir."
        raise RuntimeError(msg)


async def _main() -> int:
    load_dotenv_file(override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    _assert_dev(settings)

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            stats = await run(session)
            await session.commit()
    finally:
        await engine.dispose()

    for resource, created in stats.items():
        print(f"{resource}: +{created} created")
    logger.info("content_archive_seed_completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
