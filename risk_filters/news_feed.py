"""
Módulo de Noticias Financieras por RSS (news_feed.py)

Extrae titulares de noticias financieras de fuentes RSS gratuitas
(CNBC, Yahoo Finance). No requiere API key.

NOTA: Si se dispone de una NEWSAPI_KEY, se podría ampliar este módulo
para usar la API premium de NewsAPI.org, que ofrece más cobertura.
"""

import logging
from typing import List

try:
    import feedparser
except ImportError:
    feedparser = None

from config import RSS_FEEDS


def fetch_headlines(max_per_feed: int = 10) -> List[str]:
    """
    Descarga titulares recientes de fuentes RSS financieras.

    Args:
        max_per_feed: Número máximo de titulares por fuente RSS.

    Returns:
        Lista de strings con los titulares. Lista vacía si falla.
    """
    if feedparser is None:
        logging.warning("feedparser no instalado. Ejecuta: pip install feedparser")
        return []

    headlines: List[str] = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if title:
                    headlines.append(title)
        except Exception as e:
            logging.warning(f"Error al leer RSS {feed_url}: {e}")

    logging.info(f"Se obtuvieron {len(headlines)} titulares de {len(RSS_FEEDS)} fuentes RSS.")
    return headlines


if __name__ == "__main__":
    print("Descargando titulares de noticias financieras...\n")
    titles = fetch_headlines()
    if titles:
        for i, t in enumerate(titles, 1):
            print(f"  {i}. {t}")
    else:
        print("  No se pudieron obtener titulares.")
