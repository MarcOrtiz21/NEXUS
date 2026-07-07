"""
Filtro de Análisis de Sentimiento (sentiment.py)

Analiza titulares de noticias financieras para detectar pánico o euforia.
Usa un algoritmo de palabras clave con coincidencia de palabras completas (regex).

NOTA: Este módulo NO usa FinBERT. Para una versión con NLP real, instalar
`transformers` y `torch`, y descomentar la sección correspondiente.
"""

import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any


# Diccionarios de palabras clave con peso.
# Las palabras se buscan con regex word boundaries (\b) para evitar falsos positivos
# como "update" matcheando "up" o "supply" matcheando "down".
PANIC_WORDS = [
    "crash", "plunge", "panic", "recession", "selloff", "sell-off",
    "fear", "bear", "crisis", "collapse", "tumble", "slump", "tank",
    "meltdown", "contagion", "default", "bankruptcy",
]

BULL_WORDS = [
    "rally", "surge", "record", "boom", "bull", "growth",
    "rebound", "recovery", "breakout", "soar", "gain", "optimism",
]

PANIC_WEIGHTS = {
    "crash": 3, "plunge": 2, "panic": 3, "recession": 2, "selloff": 2,
    "sell-off": 2, "fear": 1, "bear": 1, "crisis": 3, "collapse": 3,
    "tumble": 2, "slump": 2, "tank": 2, "meltdown": 3, "contagion": 3,
    "default": 3, "bankruptcy": 3,
}

BULL_WEIGHTS = {
    "rally": 2, "surge": 2, "record": 1, "boom": 2, "bull": 1,
    "growth": 1, "rebound": 2, "recovery": 2, "breakout": 2,
    "soar": 2, "gain": 1, "optimism": 2,
}

TOPIC_KEYWORDS = {
    "Fed/tipos": ["fed", "federal reserve", "rates", "rate", "yields", "treasury", "central bank"],
    "Inflación": ["inflation", "cpi", "prices", "pce"],
    "Resultados": ["earnings", "profit", "revenue", "guidance"],
    "IA/tecnología": ["ai", "artificial intelligence", "semiconductor", "chips", "nasdaq", "tech"],
    "Recesión": ["recession", "slowdown", "unemployment", "jobs"],
    "Geopolítica": ["war", "tariff", "sanctions", "oil", "geopolitical"],
    "Divisas/dólar": ["usd", "dollar", "eur", "jpy", "gbp", "forex", "currency"],
    "Calendario macro": ["calendar", "consensus", "actual", "forecast", "gdp", "pmi", "retail sales"],
}

NEGATION_TERMS = ["not", "no", "without", "less", "eases", "ease", "avoids", "averted"]


def _count_word_hits(text: str, word_list: list) -> int:
    """Cuenta cuántas palabras de la lista aparecen como palabras completas en el texto."""
    count = 0
    text_lower = text.lower()
    for word in word_list:
        # \b asegura que matcheamos la palabra completa, no subcadenas
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            count += 1
    return count


def _matched_words(text: str, word_list: list) -> List[str]:
    """Devuelve las palabras clave encontradas en un titular."""
    text_lower = text.lower()
    return [
        word for word in word_list
        if re.search(rf"\b{re.escape(word)}\b", text_lower)
    ]


def _weighted_hits(text: str, weights: Dict[str, int]) -> tuple[int, List[str]]:
    text_lower = text.lower()
    score = 0
    matches = []
    for word, weight in weights.items():
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            matches.append(word)
            score += weight
    if matches and any(re.search(rf"\b{re.escape(term)}\b", text_lower) for term in NEGATION_TERMS):
        score = max(0, score - 1)
    return score, matches


def _detect_topics(headlines: List[str]) -> Dict[str, int]:
    joined = " ".join(headlines).lower()
    topics = {}
    for topic, terms in TOPIC_KEYWORDS.items():
        hits = sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", joined))
        if hits:
            topics[topic] = hits
    return topics


def _headline_weight(item: Dict[str, Any] | str) -> float:
    if isinstance(item, str):
        return 1.0
    return float(item.get("weight", 1.0))


def _headline_text(item: Dict[str, Any] | str) -> str:
    return item if isinstance(item, str) else str(item.get("title", ""))


def analyze_news_items(news_items: List[Dict[str, Any]]) -> Dict:
    headlines = [_headline_text(item) for item in news_items if _headline_text(item)]
    result = analyze_headlines(headlines)
    if not news_items:
        return result

    weighted_panic = 0.0
    weighted_bull = 0.0
    for item in news_items:
        title = _headline_text(item)
        if not title:
            continue
        weight = _headline_weight(item)
        panic_score, _ = _weighted_hits(title, PANIC_WEIGHTS)
        bull_score, _ = _weighted_hits(title, BULL_WEIGHTS)
        weighted_panic += panic_score * weight
        weighted_bull += bull_score * weight

    total_hits = weighted_panic + weighted_bull
    result["method"] = "weighted_keyword_regex_v3"
    result["panic_hits"] = round(weighted_panic, 2)
    result["bull_hits"] = round(weighted_bull, 2)

    if total_hits >= 3:
        panic_ratio = weighted_panic / total_hits
        result["panic_score"] = round(panic_ratio, 2)
        if panic_ratio > 0.6:
            result["dominant_sentiment"] = "PANIC"
            result["details"] = (
                f"Noticias ponderadas por fuente/recencia: miedo dominante "
                f"({weighted_panic:.1f} vs {weighted_bull:.1f}, {len(news_items)} titulares)."
            )
        elif panic_ratio < 0.4:
            result["dominant_sentiment"] = "BULLISH"
            result["details"] = (
                f"Noticias ponderadas por fuente/recencia: optimismo dominante "
                f"({weighted_bull:.1f} vs {weighted_panic:.1f}, {len(news_items)} titulares)."
            )
        else:
            result["dominant_sentiment"] = "MIXED"
            result["details"] = (
                f"Sentimiento mixto ponderado ({weighted_panic:.1f} pánico, "
                f"{weighted_bull:.1f} alcista, {len(news_items)} titulares)."
            )
    return result


def analyze_headlines(headlines: List[str]) -> Dict:
    """
    Analiza una lista de titulares financieros.

    Retorna un diccionario con:
    - panic_score: ratio de palabras de pánico vs total (0.0 a 1.0).
    - dominant_sentiment: "PANIC", "BULLISH", "MIXED" o "NEUTRAL".
    - details: explicación textual.
    """
    result = {
        "panic_score": 0.0,
        "dominant_sentiment": "NEUTRAL",
        "details": "Sin titulares para analizar.",
        "headline_count": len(headlines),
        "panic_hits": 0,
        "bull_hits": 0,
        "matched_terms": {"panic": [], "bullish": []},
        "topics": {},
        "relevance_score": 0,
        "method": "weighted_keyword_regex_v2",
    }

    if not headlines:
        return result

    total_panic = 0
    total_bull = 0

    for headline in headlines:
        panic_score, panic_matches = _weighted_hits(headline, PANIC_WEIGHTS)
        bull_score, bull_matches = _weighted_hits(headline, BULL_WEIGHTS)
        total_panic += panic_score
        total_bull += bull_score
        result["matched_terms"]["panic"].extend(panic_matches)
        result["matched_terms"]["bullish"].extend(bull_matches)

    total_hits = total_panic + total_bull
    result["panic_hits"] = total_panic
    result["bull_hits"] = total_bull
    result["matched_terms"]["panic"] = sorted(set(result["matched_terms"]["panic"]))
    result["matched_terms"]["bullish"] = sorted(set(result["matched_terms"]["bullish"]))
    result["topics"] = _detect_topics(headlines)
    result["relevance_score"] = min(100, total_hits * 10 + sum(result["topics"].values()) * 5)

    if total_hits == 0:
        if result["topics"]:
            result["details"] = f"Titulares relevantes por temas ({', '.join(result['topics'].keys())}), sin sesgo claro de pánico/euforia."
        else:
            result["details"] = f"No se detectaron palabras clave financieras en {len(headlines)} titulares."
        return result

    # Umbral mínimo: necesitamos al menos 3 señales para que sea estadísticamente relevante.
    # Con 1-2 hits, el ratio es demasiado ruidoso para bloquear el sistema.
    if total_hits < 3:
        result["details"] = f"Señales insuficientes para evaluar ({total_hits} hits en {len(headlines)} titulares). Se requieren al menos 3."
        return result

    panic_ratio = total_panic / total_hits
    result["panic_score"] = round(panic_ratio, 2)

    if panic_ratio > 0.6:
        result["dominant_sentiment"] = "PANIC"
        result["details"] = f"Noticias dominadas por miedo ({total_panic} señales de pánico vs {total_bull} alcistas, {len(headlines)} titulares)."
    elif panic_ratio < 0.4:
        result["dominant_sentiment"] = "BULLISH"
        result["details"] = f"Noticias dominadas por optimismo ({total_bull} señales alcistas vs {total_panic} de pánico, {len(headlines)} titulares)."
    else:
        result["dominant_sentiment"] = "MIXED"
        result["details"] = f"Sentimiento mixto ({total_panic} pánico, {total_bull} alcistas, {len(headlines)} titulares)."

    return result


if __name__ == "__main__":
    # Test con titulares que mezclan señales
    test = [
        "Stocks plunge as recession fears mount",
        "Tech rally gains momentum amid earnings surge",
        "Federal Reserve holds rates steady",
    ]
    print("Test de sentimiento:")
    res = analyze_headlines(test)
    for k, v in res.items():
        print(f"  {k}: {v}")
