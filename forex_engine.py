"""
Motor Forex común para NEXUS.

Centraliza la señal EUR/USD vs USD para que la CLI y el programa local no
divergan en umbrales, textos o sesgo de noticias.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from config import (
    FOREX_DIR_MODERATE,
    FOREX_DIR_STRONG,
    FOREX_NEWS_BIAS_STRONG,
    FOREX_REL_CHANGE_MODERATE,
    FOREX_REL_MOMENTUM_STRONG,
    FOREX_SCORE_MODERATE,
    FOREX_SCORE_STRONG,
    GOLD_REAL_RATE_PRESSURE,
    GOLD_REAL_RATE_SUPPORT,
    GOLD_SCORE_STRONG,
    GOLD_VIX_COMPLACENT,
    GOLD_VIX_REFUGE,
    GOLD_VIX_STRESS,
    GOLD_VS_USD_MODERATE,
    GOLD_VS_USD_STRONG,
)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def trend_from_metrics(metrics: Dict[str, Any]) -> str:
    price = _to_float(metrics.get("price"))
    ma20 = _to_float(metrics.get("ma20"))
    ma50 = _to_float(metrics.get("ma50"))
    if price is None or ma20 is None or ma50 is None:
        return "n/d"
    if price > ma20 > ma50:
        return "alcista"
    if price < ma20 < ma50:
        return "bajista"
    return "mixta"


def forex_news_bias(news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    usd_pos = (
        "hawkish", "higher rates", "inflation sticky", "risk-off", "safe haven",
        "strong dollar", "dollar strength", "fed hold", "fed hikes", "rate hike",
        "hot cpi", "strong payrolls",
    )
    usd_neg = (
        "dovish", "rate cuts", "disinflation", "soft data", "weak dollar",
        "dollar falls", "fed cut", "cool cpi", "weak payrolls",
    )
    eur_pos = (
        "ecb hawkish", "euro strength", "eurozone inflation up", "eur rallies",
        "ecb hikes", "euro rises",
    )
    eur_neg = (
        "ecb cuts", "eurozone weak", "eurozone recession", "eur weak",
        "eur drops", "euro falls",
    )

    usd_score = 0
    eur_score = 0
    for item in news_items[:60]:
        title = (item.get("title") or "").lower()
        usd_score += sum(1 for keyword in usd_pos if re.search(rf'\b{re.escape(keyword)}\b', title))
        usd_score -= sum(1 for keyword in usd_neg if re.search(rf'\b{re.escape(keyword)}\b', title))
        eur_score += sum(1 for keyword in eur_pos if re.search(rf'\b{re.escape(keyword)}\b', title))
        eur_score -= sum(1 for keyword in eur_neg if re.search(rf'\b{re.escape(keyword)}\b', title))

    net = eur_score - usd_score
    if net >= FOREX_NEWS_BIAS_STRONG:
        expectation = "Sesgo noticias favorece EURO; esperar soporte en EUR/USD."
    elif net <= -FOREX_NEWS_BIAS_STRONG:
        expectation = "Sesgo noticias favorece DOLAR; esperar presión bajista en EUR/USD."
    else:
        expectation = "Sesgo noticias mixto; esperar lateralidad y volatilidad."

    return {
        "usd_score": usd_score,
        "eur_score": eur_score,
        "net_eur_minus_usd": net,
        "expectation": expectation,
    }


def forex_signal(
    fx_metrics: Dict[str, Any],
    uup_metrics: Dict[str, Any],
    news_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    eur_1m = _to_float(fx_metrics.get("momentum_1m"))
    eur_3m = _to_float(fx_metrics.get("momentum_3m"))
    usd_1m = _to_float(uup_metrics.get("momentum_1m"))
    usd_3m = _to_float(uup_metrics.get("momentum_3m"))
    eur_trend = trend_from_metrics(fx_metrics)
    usd_trend = trend_from_metrics(uup_metrics)

    # Si falta algún dato clave de momentum, no fabricar señal falsa.
    if eur_1m is None or usd_1m is None:
        rel_1m = None
    else:
        rel_1m = eur_1m - usd_1m

    if eur_3m is None or usd_3m is None:
        rel_3m = None
    else:
        rel_3m = eur_3m - usd_3m

    rel_change = None
    if rel_1m is not None and rel_3m is not None:
        rel_change = rel_1m - rel_3m

    evolution = "estable"
    if rel_change is not None:
        if rel_change > FOREX_REL_MOMENTUM_STRONG:
            evolution = "EURO gana fuerza frente a DOLAR"
        elif rel_change < -FOREX_REL_MOMENTUM_STRONG:
            evolution = "DOLAR gana fuerza frente a EURO"

    news = forex_news_bias(news_items)

    score = 0
    if rel_1m is not None:
        if rel_1m > FOREX_REL_MOMENTUM_STRONG:
            score += 2
        elif rel_1m < -FOREX_REL_MOMENTUM_STRONG:
            score -= 2
    if rel_change is not None:
        if rel_change > FOREX_REL_CHANGE_MODERATE:
            score += 1
        elif rel_change < -FOREX_REL_CHANGE_MODERATE:
            score -= 1
    if eur_trend == "alcista" and usd_trend != "alcista":
        score += 1
    elif usd_trend == "alcista" and eur_trend != "alcista":
        score -= 1
    if news["net_eur_minus_usd"] >= FOREX_NEWS_BIAS_STRONG:
        score += 1
    elif news["net_eur_minus_usd"] <= -FOREX_NEWS_BIAS_STRONG:
        score -= 1

    if score >= FOREX_SCORE_STRONG:
        action = "COMPRAR EURO / VENDER DOLAR"
        confidence = "ALTA"
    elif score <= -FOREX_SCORE_STRONG:
        action = "COMPRAR DOLAR / VENDER EURO"
        confidence = "ALTA"
    elif score >= FOREX_SCORE_MODERATE:
        action = "MANTENER SESGO EURO"
        confidence = "MEDIA"
    elif score <= -FOREX_SCORE_MODERATE:
        action = "MANTENER SESGO DOLAR"
        confidence = "MEDIA"
    else:
        action = "MANTENER / ESPERAR"
        confidence = "BAJA"

    return {
        "action": action,
        "confidence": confidence,
        "score": score,
        "eur_trend": eur_trend,
        "usd_trend": usd_trend,
        "rel_1m": rel_1m,
        "rel_3m": rel_3m,
        "rel_change": rel_change,
        "evolution": evolution,
        "news": news,
    }


def forex_leg_strength(metrics: Dict[str, Any] | None) -> int | None:
    """Fortaleza 0–100 de una pata FX a partir de precio, medias y momentum. None si no hay datos."""
    metrics = metrics or {}
    price = _to_float(metrics.get("price"))
    mom1 = _to_float(metrics.get("momentum_1m"))
    mom3 = _to_float(metrics.get("momentum_3m"))
    if price is None and mom1 is None:
        return None
    score = 50.0
    trend = trend_from_metrics(metrics)
    if trend == "alcista":
        score += 12
    elif trend == "bajista":
        score -= 12
    if mom1 is not None:
        score += max(-25.0, min(25.0, mom1 * 8))
    if mom3 is not None:
        score += max(-12.0, min(12.0, mom3 * 3))
    return int(max(0, min(100, round(score))))


def forex_pair_strength(
    fx_metrics: Dict[str, Any] | None,
    uup_metrics: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Fortaleza del euro y del dólar por separado. Un 50 es neutro, no ausencia de datos."""
    eur = forex_leg_strength(fx_metrics)
    usd = forex_leg_strength(uup_metrics)
    return {"eur": eur, "usd": usd}


def forex_semaphore(score: int) -> Dict[str, str]:
    if score >= FOREX_SCORE_STRONG:
        return {"color": "green", "label": "VERDE", "description": "Sesgo fuerte pro EURO"}
    if score >= FOREX_SCORE_MODERATE:
        return {"color": "yellow", "label": "AMARILLO", "description": "Sesgo moderado pro EURO"}
    if score <= -FOREX_SCORE_STRONG:
        return {"color": "red", "label": "ROJO", "description": "Sesgo fuerte pro DOLAR"}
    if score <= -FOREX_SCORE_MODERATE:
        return {"color": "orange", "label": "NARANJA", "description": "Sesgo moderado pro DOLAR"}
    return {"color": "neutral", "label": "NEUTRO", "description": "Sin ventaja clara"}


def forex_dual_perspective(signal: Dict[str, Any]) -> Dict[str, str]:
    score = signal.get("score", 0)
    if score >= FOREX_SCORE_STRONG:
        eur_view = "COMPRAR EURO frente a DOLAR"
        usd_view = "VENDER DOLAR frente a EURO"
    elif score >= FOREX_SCORE_MODERATE:
        eur_view = "MANTENER sesgo EURO frente a DOLAR"
        usd_view = "MANTENER DOLAR defensivo"
    elif score <= -FOREX_SCORE_STRONG:
        eur_view = "VENDER EURO frente a DOLAR"
        usd_view = "COMPRAR DOLAR frente a EURO"
    elif score <= -FOREX_SCORE_MODERATE:
        eur_view = "MANTENER EURO defensivo"
        usd_view = "MANTENER sesgo DOLAR frente a EURO"
    else:
        eur_view = "MANTENER / ESPERAR"
        usd_view = "MANTENER / ESPERAR"
    return {"eur_view": eur_view, "usd_view": usd_view}


def directional_forex_semaphore(score_for_direction: float) -> Dict[str, str]:
    if score_for_direction >= FOREX_DIR_STRONG:
        return {"color": "green", "label": "VERDE", "strength": "fuerte"}
    if score_for_direction >= FOREX_DIR_MODERATE:
        return {"color": "yellow", "label": "AMARILLO", "strength": "moderado"}
    if score_for_direction <= -FOREX_DIR_STRONG:
        return {"color": "red", "label": "ROJO", "strength": "fuerte"}
    if score_for_direction <= -FOREX_DIR_MODERATE:
        return {"color": "orange", "label": "NARANJA", "strength": "moderado"}
    return {"color": "neutral", "label": "NEUTRO", "strength": "mixto"}


def forex_bidirectional_rates(fx_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula tipos de cambio bidireccionales a partir del spot EUR/USD.

    Si EUR/USD = 1.12, entonces USD/EUR = 1/1.12 ≈ 0.8929.
    El usuario pidió ver ambos lados del tipo de cambio real.
    """
    eur_usd = _to_float(fx_metrics.get("price"))
    if eur_usd is None or eur_usd <= 0:
        return {
            "eur_usd": None,
            "usd_eur": None,
            "eur_label": "1 EUR = — USD",
            "usd_label": "1 USD = — EUR",
        }

    usd_eur = 1.0 / eur_usd
    return {
        "eur_usd": round(eur_usd, 4),
        "usd_eur": round(usd_eur, 4),
        "eur_label": f"1 EUR = {eur_usd:.4f} USD",
        "usd_label": f"1 USD = {usd_eur:.4f} EUR",
    }


def gold_signal(
    gld_metrics: Dict[str, Any],
    uup_metrics: Dict[str, Any],
    *,
    vix: float | None = None,
    us10y: float | None = None,
    cpi_yoy: float | None = None,
) -> Dict[str, Any]:
    """Sesgo de oro: refugio, presión o mixto según dólar, tipos reales y VIX."""
    gld_1m = _to_float((gld_metrics or {}).get("momentum_1m"))
    usd_1m = _to_float((uup_metrics or {}).get("momentum_1m"))
    gld_trend = trend_from_metrics(gld_metrics or {})
    usd_trend = trend_from_metrics(uup_metrics or {})
    vix_value = _to_float(vix)
    us10y_value = _to_float(us10y)
    cpi_value = _to_float(cpi_yoy)

    vs_dollar = None
    if gld_1m is not None and usd_1m is not None:
        vs_dollar = round(gld_1m - usd_1m, 2)

    real_rate = None
    if us10y_value is not None and cpi_value is not None:
        real_rate = round(us10y_value - cpi_value, 2)

    score = 0
    inputs = 0
    drivers: List[str] = []

    if gld_trend == "alcista":
        score += 1
        inputs += 1
        drivers.append("Tendencia de GLD alcista.")
    elif gld_trend == "bajista":
        score -= 1
        inputs += 1
        drivers.append("Tendencia de GLD bajista.")

    if vs_dollar is not None:
        inputs += 1
        if vs_dollar >= GOLD_VS_USD_STRONG:
            score += 2
            drivers.append("El oro gana al dólar a 1 mes.")
        elif vs_dollar >= GOLD_VS_USD_MODERATE:
            score += 1
            drivers.append("Ligera ventaja del oro frente al dólar.")
        elif vs_dollar <= -GOLD_VS_USD_STRONG:
            score -= 2
            drivers.append("El dólar gana al oro a 1 mes.")
        elif vs_dollar <= -GOLD_VS_USD_MODERATE:
            score -= 1
            drivers.append("Ligera presión del dólar sobre el oro.")

    if real_rate is not None:
        inputs += 1
        if real_rate <= GOLD_REAL_RATE_SUPPORT:
            score += 2
            drivers.append(f"Tipos reales bajos ({real_rate:.2f}%).")
        elif real_rate >= GOLD_REAL_RATE_PRESSURE:
            score -= 2
            drivers.append(f"Tipos reales altos ({real_rate:.2f}%) presionan el oro.")
        else:
            drivers.append(f"Tipos reales intermedios ({real_rate:.2f}%).")

    if vix_value is not None:
        inputs += 1
        if vix_value >= GOLD_VIX_STRESS:
            score += 2
            drivers.append(f"VIX en {vix_value:.1f}: demanda de refugio.")
        elif vix_value >= GOLD_VIX_REFUGE:
            score += 1
            drivers.append(f"VIX elevado ({vix_value:.1f}).")
        elif vix_value < GOLD_VIX_COMPLACENT:
            score -= 1
            drivers.append(f"VIX contenido ({vix_value:.1f}): menos refugio.")

    if score >= GOLD_SCORE_STRONG:
        bias = "REFUGIO"
        tone = "GOOD"
        summary = "El oro se comporta como refugio: dólar, tipos o estrés lo favorecen."
    elif score <= -GOLD_SCORE_STRONG:
        bias = "PRESION"
        tone = "BAD"
        summary = "El dólar y los tipos reales presionan el oro; no perseguir el rebote."
    else:
        bias = "MIXTO"
        tone = "WARN"
        summary = "Lectura mixta: el oro no tiene una ventaja clara frente al dólar y los tipos."

    if inputs <= 1:
        confidence = "BAJA"
    elif inputs <= 2:
        confidence = "MEDIA"
    else:
        confidence = "ALTA"

    if gld_1m is None or usd_1m is None:
        vs_dollar_note = "Falta el momentum 1M de GLD o UUP para comparar con el dólar."
    elif gld_1m > 0 and usd_1m > 0:
        vs_dollar_note = "Oro y dólar suben a la vez; el relativo importa más que el precio."
    elif gld_1m > 0 and usd_1m < 0:
        vs_dollar_note = "El oro gana con dólar débil."
    elif gld_1m < 0 and usd_1m > 0:
        vs_dollar_note = "El dólar presiona al oro."
    else:
        vs_dollar_note = "Ambos retroceden a 1 mes; el relativo no cambia la tesis por sí solo."

    return {
        "bias": bias,
        "tone": tone,
        "summary": summary,
        "confidence": confidence,
        "score": score,
        "real_rate": real_rate,
        "vs_dollar_1m": vs_dollar,
        "vs_dollar_note": vs_dollar_note,
        "vix": vix_value,
        "gld_trend": gld_trend,
        "usd_trend": usd_trend,
        "drivers": drivers[:4],
    }
