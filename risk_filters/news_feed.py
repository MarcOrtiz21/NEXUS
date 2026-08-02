"""
Módulo de Noticias Financieras (news_feed.py)

Extrae titulares de RSS gratuitos y, opcionalmente, de NewsAPI.
"""

from __future__ import annotations

import logging
import re
from html import unescape
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any

try:
    import feedparser
except ImportError:
    feedparser = None

import requests

from config import RSS_FEEDS, NEWSAPI_KEY
from risk_filters.sentiment import enrich_news_items_with_tone

LOW_RELEVANCE_CALENDAR_TERMS = [
    "national day", "holiday", "bank holiday", "constitution day", "independence day",
    "victory day", "labor day", "labour day",
]

HIGH_RELEVANCE_TERMS = [
    "fed", "fomc", "cpi", "inflation", "pce", "gdp", "payroll", "nfp",
    "unemployment", "pmi", "retail sales", "rate decision", "interest rate",
    "jobless claims", "ism", "consumer confidence",
]

LINKED_TOPIC_TERMS = {
    "Fed/tipos": ["fed", "federal reserve", "fomc", "interest rate", "treasury yield"],
    "Inflación": ["inflation", "cpi", "pce"],
    "Resultados": ["earnings", "revenue", "profit", "guidance"],
    "IA/tecnología": ["artificial intelligence", "semiconductor", "chip"],
    "Recesión/empleo": ["recession", "unemployment", "payroll", "jobless claims"],
    "Geopolítica": ["tariff", "sanction", "geopolitical", "war"],
    "Divisas": ["forex", "currency", "exchange rate"],
    "Asia": ["china", "japan", "korea", "taiwan", "asia", "beijing", "tokyo", "seoul"],
}

LINKED_ASSET_TERMS = {
    "SPY": ["spy", "s&p 500", "s&p500"],
    "QQQ": ["qqq", "nasdaq 100", "nasdaq-100"],
    "TLT": ["tlt", "long-term treasury", "long dated treasury"],
    "GLD": ["gld", "gold", "bullion"],
    "UUP": ["uup", "dollar index", "dxy"],
    "EURUSD": ["eur/usd", "eurusd", "euro-dollar"],
}


def _feed_name(feed_config) -> str:
    return feed_config.get("name", feed_config.get("url", "RSS")) if isinstance(feed_config, dict) else str(feed_config)


def _feed_url(feed_config) -> str:
    return feed_config.get("url", "") if isinstance(feed_config, dict) else str(feed_config)


def _feed_weight(feed_config) -> float:
    if isinstance(feed_config, dict):
        return float(feed_config.get("weight", 1.0))
    return 1.0


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _clean_text(value: Any, max_length: int = 600) -> str | None:
    """Elimina HTML y acota texto editorial para el contrato nativo."""
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", unescape(str(value)))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return text if len(text) <= max_length else text[:max_length - 1].rstrip() + "…"


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", text.lower()))


def _link_news_context(title: Any, summary: Any = None, description: Any = None) -> Dict[str, Any]:
    """Asocia temas/activos explícitos; describe relación, nunca causalidad."""
    text = " ".join(str(value or "") for value in (title, summary, description))
    topics = [
        topic for topic, terms in LINKED_TOPIC_TERMS.items()
        if any(_contains_term(text, term) for term in terms)
    ]
    assets = [
        ticker for ticker, terms in LINKED_ASSET_TERMS.items()
        if any(_contains_term(text, term) for term in terms)
    ]
    return {
        "linked_topics": topics,
        "linked_assets": assets,
        "linkage_method": "explicit_keyword_heuristic",
        "linkage_note": "Coincidencia contextual; no implica causalidad ni impacto.",
    }


def _enrich_item_context(item: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(item)
    row["summary"] = _clean_text(row.get("summary"))
    row["description"] = _clean_text(row.get("description"))
    row.update(_link_news_context(row.get("title"), row["summary"], row["description"]))
    return row


def _parse_published(entry) -> str | None:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def _is_relevant_item(title: str, source: str) -> bool:
    title_lower = title.lower()
    source_lower = source.lower()
    if "economic calendar" not in source_lower:
        return True
    if any(term in title_lower for term in LOW_RELEVANCE_CALENDAR_TERMS):
        return False
    return any(term in title_lower for term in HIGH_RELEVANCE_TERMS)


def _recency_weight(published_at: str | None) -> float:
    if not published_at:
        return 0.75
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_hours = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
        if age_hours <= 6:
            return 1.5
        if age_hours <= 24:
            return 1.2
        if age_hours <= 72:
            return 1.0
        return 0.6
    except Exception:
        return 0.75


def _published_sort_key(item: Dict[str, Any]) -> float:
    """Timestamp para ordenar; artículos sin fecha permanecen al final."""
    raw = item.get("published_at") or item.get("captured_at")
    if not raw:
        return 0.0
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _diversify_by_source(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Intercala titulares recientes por fuente antes de que la UI los limite."""
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for item in sorted(items, key=_published_sort_key, reverse=True):
        by_source.setdefault(str(item.get("source") or "RSS"), []).append(item)

    source_order = sorted(
        by_source,
        key=lambda source: _published_sort_key(by_source[source][0]),
        reverse=True,
    )
    result: List[Dict[str, Any]] = []
    while any(by_source.values()):
        for source in source_order:
            if by_source[source]:
                result.append(by_source[source].pop(0))
    return result


def _fetch_newsapi_items(max_items: int = 20) -> List[Dict[str, Any]]:
    if not NEWSAPI_KEY:
        return []

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "category": "business",
        "language": "en",
        "pageSize": max_items,
        "apiKey": NEWSAPI_KEY,
    }
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        items = []
        for article in payload.get("articles", []):
            title = (article.get("title") or "").strip()
            if not title or title.endswith(" - Removed"):
                continue
            published_at = article.get("publishedAt")
            description = _clean_text(article.get("description"))
            items.append(_enrich_item_context({
                "title": title,
                "source": article.get("source", {}).get("name", "NewsAPI"),
                "url": article.get("url", ""),
                "published_at": published_at,
                "captured_at": captured_at,
                "weight": 1.3,
                "provider": "newsapi",
                "summary": description,
                "description": description,
            }))
        logging.info(f"NewsAPI aportó {len(items)} titulares.")
        return items
    except Exception as exc:
        logging.warning(f"Error al consultar NewsAPI: {exc}")
        return []


def fetch_news_items(max_per_feed: int = 10) -> List[Dict[str, Any]]:
    """
    Descarga titulares con metadata trazable, pesos por fuente y recencia.
    """
    if feedparser is None:
        logging.warning("feedparser no instalado. Ejecuta: pip install feedparser")
        rss_items: List[Dict[str, Any]] = []
    else:
        rss_items = []
        seen = set()
        captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        for feed_config in RSS_FEEDS:
            feed_url = _feed_url(feed_config)
            source = _feed_name(feed_config)
            base_weight = _feed_weight(feed_config)
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
                    published_at = _parse_published(entry)
                    rss_items.append(_enrich_item_context({
                        "title": title,
                        "source": source,
                        "url": entry.get("link", ""),
                        "published_at": published_at,
                        "captured_at": captured_at,
                        "weight": base_weight * _recency_weight(published_at),
                        "provider": "rss",
                        "summary": entry.get("summary"),
                        "description": entry.get("description"),
                    }))
            except Exception as exc:
                logging.warning(f"Error al leer RSS {source}: {exc}")

    api_items = _fetch_newsapi_items()
    merged: List[Dict[str, Any]] = []
    seen = set()
    for item in api_items + rss_items:
        key = _normalize_title(item["title"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    merged = _diversify_by_source(merged)
    logging.info(f"Se obtuvieron {len(merged)} titulares únicos ({len(api_items)} NewsAPI + {len(rss_items)} RSS).")
    return enrich_news_items_with_tone(merged)


def fetch_headlines(max_per_feed: int = 10) -> List[str]:
    return [item["title"] for item in fetch_news_items(max_per_feed=max_per_feed)]


if __name__ == "__main__":
    print("Descargando titulares de noticias financieras...\n")
    for i, item in enumerate(fetch_news_items(), 1):
        print(f"  {i}. [{item['source']}] ({item['weight']:.2f}) {item['title']}")
