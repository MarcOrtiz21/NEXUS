"""
Módulo de Noticias Financieras por RSS (news_feed.py)

Extrae titulares de noticias financieras de fuentes RSS gratuitas
(CNBC, Yahoo Finance). No requiere API key.

NOTA: Si se dispone de una NEWSAPI_KEY, se podría ampliar este módulo
para usar la API premium de NewsAPI.org, que ofrece más cobertura.
"""

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any

try:
    import feedparser
except ImportError:
    feedparser = None

from config import RSS_FEEDS

LOW_RELEVANCE_CALENDAR_TERMS = [
    "national day", "holiday", "bank holiday", "constitution day", "independence day",
    "victory day", "labor day", "labour day",
]

HIGH_RELEVANCE_TERMS = [
    "fed", "fomc", "cpi", "inflation", "pce", "gdp", "payroll", "nfp",
    "unemployment", "pmi", "retail sales", "rate decision", "interest rate",
    "jobless claims", "ism", "consumer confidence",
]


def _feed_name(feed_config) -> str:
    return feed_config.get("name", feed_config.get("url", "RSS")) if isinstance(feed_config, dict) else str(feed_config)


def _feed_url(feed_config) -> str:
    return feed_config.get("url", "") if isinstance(feed_config, dict) else str(feed_config)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _parse_published(entry) -> str | None:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None


def _is_relevant_item(title: str, source: str) -> bool:
    title_lower = title.lower()
    source_lower = source.lower()
    if "economic calendar" not in source_lower:
        return True
    if any(term in title_lower for term in LOW_RELEVANCE_CALENDAR_TERMS):
        return False
    return any(term in title_lower for term in HIGH_RELEVANCE_TERMS)
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def fetch_news_items(max_per_feed: int = 10) -> List[Dict[str, Any]]:
    """
    Descarga titulares con metadata trazable: fuente, URL y fecha si el RSS la aporta.
    Deduplica por título normalizado.
    """
    if feedparser is None:
        logging.warning("feedparser no instalado. Ejecuta: pip install feedparser")
        return []

    seen = set()
    items: List[Dict[str, Any]] = []
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for feed_config in RSS_FEEDS:
        feed_url = _feed_url(feed_config)
        source = _feed_name(feed_config)
        if not feed_url:
            continue
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                if not _is_relevant_item(title, source):
                    continue
                key = _normalize_title(title)
                if key in seen:
                    continue
                seen.add(key)
                items.append({
                    "title": title,
                    "source": source,
                    "url": entry.get("link", ""),
                    "published_at": _parse_published(entry),
                    "captured_at": captured_at,
                })
        except Exception as e:
            logging.warning(f"Error al leer RSS {source}: {e}")

    logging.info(f"Se obtuvieron {len(items)} titulares únicos de {len(RSS_FEEDS)} fuentes RSS.")
    return items


def fetch_headlines(max_per_feed: int = 10) -> List[str]:
    """
    Descarga titulares recientes de fuentes RSS financieras.

    Args:
        max_per_feed: Número máximo de titulares por fuente RSS.

    Returns:
        Lista de strings con los titulares. Lista vacía si falla.
    """
    return [item["title"] for item in fetch_news_items(max_per_feed=max_per_feed)]


if __name__ == "__main__":
    print("Descargando titulares de noticias financieras...\n")
    titles = fetch_headlines()
    if titles:
        for i, t in enumerate(titles, 1):
            print(f"  {i}. {t}")
    else:
        print("  No se pudieron obtener titulares.")
