"""Geçici in-memory log yakalama (Faz 6.1).

Pipeline adımı süresince ilgili logger'ların (örn. `ygip.ai_engine.*`) kayıtlarını
toplayıp adım `detail` (JSONB) içinde saklamak için kullanılır — böylece bülten
üretimi sırasında LLM/pipeline kodunun ürettiği loglar admin "Pipeline Run Detayı"
ekranında görünür.

Handler yalnızca `capture_logs` bağlamı boyunca eklidir; çıkışta sökülür ve
logger seviyeleri eski haline döner. Tek process içinde eşzamanlı iki üretim
loglarını karıştırabilir; pipeline adımları sıralı koştuğundan pratikte sorun değil.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

# `extra=` ile gelen alanları ayıklamak için standart LogRecord alan kümesi.
_STANDARD_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def _coerce(value: Any) -> Any:
    """JSONB'ye güvenle yazılabilir skalere indirger."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class ListLogHandler(logging.Handler):
    """Kayıtları bellek içi bir listeye (JSONB-uyumlu dict) toplayan handler."""

    def __init__(self, *, limit: int) -> None:
        super().__init__()
        self.records: list[dict[str, Any]] = []
        self.dropped = 0
        self._limit = limit

    def emit(self, record: logging.LogRecord) -> None:
        if len(self.records) >= self._limit:
            self.dropped += 1
            return
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - format hatası logu düşürmesin
            message = record.msg if isinstance(record.msg, str) else repr(record.msg)
        context = {
            key: _coerce(value)
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_ATTRS
        }
        entry: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
        }
        if context:
            entry["context"] = context
        if record.exc_info:
            entry["exc"] = self.format(record)
        self.records.append(entry)


@contextmanager
def capture_logs(
    logger_names: Sequence[str],
    *,
    level: int = logging.INFO,
    limit: int = 500,
) -> Iterator[ListLogHandler]:
    """`logger_names` altındaki kayıtları bağlam süresince yakalar.

    Hedef logger'ların efektif seviyesi `level`'dan yüksekse geçici olarak
    düşürülür (aksi halde INFO kaydı hiç oluşmaz), çıkışta geri yüklenir.
    """
    handler = ListLogHandler(limit=limit)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter())
    targets = [logging.getLogger(name) for name in logger_names]

    # `disable_existing_loggers=True` (örn. alembic `fileConfig`) mevcut `ygip.*`
    # logger'larını `disabled=True` yapabilir; bu kayıt oluşumunu logger seviyesinden
    # bağımsız susturur. Yakalama süresince hedef logger + mevcut alt-logger'ları
    # yeniden etkinleştir, çıkışta eski haline döndür.
    managed: dict[logging.Logger, bool] = {}
    for name in logger_names:
        prefix = f"{name}."
        for lname, candidate in logging.root.manager.loggerDict.items():
            if isinstance(candidate, logging.Logger) and (
                lname == name or lname.startswith(prefix)
            ):
                managed.setdefault(candidate, candidate.disabled)
    for target in targets:
        managed.setdefault(target, target.disabled)

    previous_levels = {lg: lg.level for lg in targets}
    # Global `logging.disable(...)` bu eşiğin altındaki kayıtları susturur — kaldır.
    previous_disable = logging.root.manager.disable
    if previous_disable >= level:
        logging.disable(logging.NOTSET)
    for lg in managed:
        lg.disabled = False
    for lg in targets:
        if lg.getEffectiveLevel() > level:
            lg.setLevel(level)
        lg.addHandler(handler)
    try:
        yield handler
    finally:
        for lg in targets:
            lg.removeHandler(handler)
            lg.setLevel(previous_levels[lg])
        for lg, was_disabled in managed.items():
            lg.disabled = was_disabled
        if previous_disable >= level:
            logging.disable(previous_disable)
