"""DB tabanlı gözlem yardımcıları — ingest sayımı + aktif kaynak tipi çözümleme (Faz 6.1).

`IngestStageExecutor` ve `CollectStageExecutor`'ın gerçek (DB) bağımlılıkları. Orkestratör
kendi `session_factory`'sini kullanır (background driver; request session'ına bağlı değil —
`Docs/04` §10.5). Yalnızca okuma; collector/processor verisine yazmaz. Raw SQL yok.
"""

from __future__ import annotations

from packages.shared.enums import RawItemStatus, SourceStatus, SourceType
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbRawItemCounter:
    """Bu run'a ait `raw_items` sayısını döner (`fetched_at >= run.started_at`).

    Statüden bağımsız sayar: ingest aşaması koşarken processor bazı kayıtları zaten
    `processing`/`processed`'a taşımış olabilir — `fetched_at` penceresi bu run'da
    ingest edilen toplam ham kaydı verir (`Docs/04` §10.5 ingest kriteri).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def count_ingested(self, run: PipelineRun) -> int:
        if run.started_at is None:
            return 0
        async with self._session_factory() as db:
            result = await db.execute(
                select(func.count())
                .select_from(RawItem)
                .where(RawItem.fetched_at >= run.started_at)
            )
            return int(result.scalar_one())


class DbProcessedItemCounter:
    """Bu run'da işlenen toplam `processed_items` sayısını 5 schema'da toplar.

    `processed_items` schema-partition'lıdır (`news`/`market`/`geo`/`transport`/`fmcg` —
    `Docs/02` §2); her tablo `processed_at >= run.started_at` penceresiyle sayılıp
    toplanır. `ProcessStageExecutor` bu artışı SQS drain ile çapraz doğrular (`Docs/04`
    §10.5). Yalnızca okuma; processor verisine yazmaz. Raw SQL yok.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def count_processed(self, run: PipelineRun) -> int:
        if run.started_at is None:
            return 0
        total = 0
        async with self._session_factory() as db:
            for model in PROCESSED_ITEM_MODELS.values():
                result = await db.execute(
                    select(func.count())
                    .select_from(model)
                    .where(model.processed_at >= run.started_at)
                )
                total += int(result.scalar_one())
        return total


class DbRawItemFailedCounter:
    """Bu run'da processor'ın **gerçekten başarısız** saydığı `raw_items` sayısı.

    Gate/dedup ile elenen kayıtlar `PROCESSED` işaretlenir (içerik üretmedi ama hata
    değil — `raw_item_lifecycle`); yalnızca pipeline exception'ı / persist hatası
    `FAILED` olur. `ProcessStageExecutor` bu sayıyı "Hatalı"ya, kalan farkı
    "Elendi"ye yazar — böylece filtreleme hata olarak görünmez (`Docs/04` §10.5).
    Yalnızca okuma; raw SQL yok.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def count_failed(self, run: PipelineRun) -> int:
        if run.started_at is None:
            return 0
        async with self._session_factory() as db:
            result = await db.execute(
                select(func.count())
                .select_from(RawItem)
                .where(
                    RawItem.fetched_at >= run.started_at,
                    RawItem.status == RawItemStatus.FAILED,
                )
            )
            return int(result.scalar_one())


class DbActiveTypesResolver:
    """`["all"]` tetiğinde aktif kaynakların sahip olduğu distinct tipleri döner."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(self) -> list[str]:
        async with self._session_factory() as db:
            result = await db.execute(
                select(Source.source_type)
                .where(Source.status == SourceStatus.ACTIVE)
                .distinct()
            )
            return [
                value.value if isinstance(value, SourceType) else str(value)
                for value in result.scalars().all()
            ]
