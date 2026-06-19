"""Collector worker paketi — veri toplama Lambda'ları."""

from services.collectors.base_collector import BaseCollector
from services.collectors.email_collector import EmailCollector
from services.collectors.gov_collector import GovCollector
from services.collectors.handler import COLLECTOR_MAP, register_collector
from services.collectors.models import NormalizedArticle, RawArticle
from services.collectors.rss_collector import RSSCollector

__all__ = [
    "BaseCollector",
    "COLLECTOR_MAP",
    "EmailCollector",
    "GovCollector",
    "NormalizedArticle",
    "RSSCollector",
    "RawArticle",
    "register_collector",
]
