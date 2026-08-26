"""Derived, explainable diagnostics used by the native decision interface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from config import (
    VIX_ACCELERATION_PCT,
    VIX_CALM_THRESHOLD,
    VIX_ELEVATED_THRESHOLD,
    VIX_PANIC_THRESHOLD,
)


def _number(data: Dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def classify_vix_regime(vix: float | None, vix_ma20: float | None = None) -> Dict[str, Any]:
    """Un solo régimen de VIX para el score. No suma puntos brutos ni duplica CAUTION/HEALTHY.

    Bandas = constantes de config (calma / elevado / pánico) más aceleración vs MA20.
    """
    if vix is None:
        return {
            "label": "DESCONOCIDO",
            "tone": "neutral",
            "multiplier": 1.0,
            "penalty": 0,
            "reason": None,
        }
    accelerating = (
        vix_ma20 is not None
        and vix_ma20 > 0
        and vix > vix_ma20 * (1.0 + VIX_ACCELERATION_PCT)
    )
    if vix >= VIX_PANIC_THRESHOLD:
        return {
            "label": "ESTRÉS",
            "tone": "bad",
            "multiplier": 0.25,
            "penalty": 12,
            "reason": "régimen VIX de estrés: comprime el sesgo alcista",
        }
    if vix >= VIX_ELEVATED_THRESHOLD or (vix >= VIX_CALM_THRESHOLD and accelerating):
        return {
            "label": "CAUTELA",
            "tone": "warn",
            "multiplier": 0.5,
            "penalty": 6,
            "reason": "régimen VIX de cautela: reduce el sesgo alcista",
        }
    if vix < VIX_CALM_THRESHOLD:
        return {
            "label": "CALMA",
            "tone": "good",
            "multiplier": 1.0,
            "penalty": 0,
            "reason": "régimen VIX de calma",
        }
    return {
        "label": "NORMAL",
        "tone": "neutral",
        "multiplier": 1.0,
        "penalty": 0,
        "reason": "régimen VIX normal",
    }


def classify_market_regime(data: Dict[str, Any]) -> Dict[str, Any]:
    """Classify market context without treating it as an execution signal."""
    vix, vix_ma20 = _number(data, "VIX"), _number(data, "VIX_MA20")
    spy = (data.get("Assets") or {}).get("SPY") or {}
    momentum = spy.get("momentum_1m")
    price, ma50 = spy.get("price"), spy.get("ma50")
    if vix is not None and vix >= 28:
        regime, tone = "ESTRÉS", "bad"
    elif vix is not None and vix_ma20 and vix > vix_ma20 * 1.15:
        regime, tone = "CAUTELA", "warn"
    elif isinstance(momentum, (int, float)) and momentum > 0 and price and ma50 and price >= ma50:
        regime, tone = "EXPANSIÓN", "good"
    elif isinstance(momentum, (int, float)) and momentum < 0 and price and ma50 and price < ma50:
        regime, tone = "DESACELERACIÓN", "warn"
    else:
        regime, tone = "TRANSICIÓN", "neutral"
    return {
        "label": regime,
        "tone": tone,
        "vix": vix,
        "spy_momentum_1m": momentum,
        "summary": "Contexto descriptivo basado en volatilidad y tendencia; no sustituye la decisión operativa.",
    }


def score_attribution(data: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Explain observable inputs behind the score; weights are deliberately not invented."""
    assets = data.get("Assets") or {}
    spy = assets.get("SPY") or {}
    factors = [
        {"label": "Tendencia SPY", "value": spy.get("momentum_1m"), "unit": "% 1M"},
        {"label": "Volatilidad (VIX)", "value": data.get("VIX"), "unit": "nivel"},
        {"label": "Curva 10Y–2Y", "value": data.get("Yield_Curve_Spread"), "unit": "pp"},
        {"label": "Inflación", "value": data.get("CPI_YoY_Pct"), "unit": "%"},
    ]
    return {
        "score": decision.get("score"),
        "factors": [item for item in factors if item["value"] is not None],
        "note": "Muestra los factores observables disponibles; el score final incorpora reglas del motor.",
    }


def detect_market_anomalies(data: Dict[str, Any]) -> list[Dict[str, Any]]:
    checks = [
        ("VIX", _number(data, "VIX"), 28, "Volatilidad elevada"),
        ("VIX vs MA20", _ratio(data, "VIX", "VIX_MA20"), 0.15, "VIX muy por encima de su media"),
        ("Curva 10Y–2Y", _number(data, "Yield_Curve_Spread"), -0.25, "Curva invertida"),
        ("SPY momentum 1M", ((data.get("Assets") or {}).get("SPY") or {}).get("momentum_1m"), -5, "Caída mensual relevante"),
    ]
    anomalies = []
    for label, value, threshold, title in checks:
        if value is None:
            continue
        triggered = value >= threshold if label.startswith("VIX") else value <= threshold
        if triggered:
            anomalies.append({"label": label, "value": round(float(value), 2), "title": title, "severity": "warn"})
    return anomalies


def _ratio(data: Dict[str, Any], numerator: str, denominator: str) -> float | None:
    a, b = _number(data, numerator), _number(data, denominator)
    return (a / b - 1) if a is not None and b not in (None, 0) else None


def data_quality_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    quality = data.get("DataQuality") or {}
    counts: Dict[str, int] = {}
    for item in quality.values():
        status = str((item or {}).get("status") or "UNKNOWN").upper()
        counts[status] = counts.get(status, 0) + 1
    unhealthy = sum(count for status, count in counts.items() if status not in {"OK", "FRESH"})
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(quality),
        "unhealthy": unhealthy,
        "status_counts": counts,
        "critical": [key for key, item in quality.items() if str((item or {}).get("status")).upper() in {"ERROR", "MISSING"}][:8],
        "observations": {
            key: (quality.get(key) or {}).get("as_of")
            for key in ("CPI_YoY_Pct", "M2_Change_Pct", "China_M2_YoY_Pct", "US2Y")
            if (quality.get(key) or {}).get("as_of")
        },
    }


def format_obs_date(value: str | None) -> str:
    """Fecha de observación FRED en etiqueta corta (no es la captura NEXUS)."""
    if not value:
        return ""
    raw = str(value)[:10]
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return raw
    months = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{parsed.day} {months[parsed.month - 1]}"


def format_age_label(age_seconds: float | int | None) -> str:
    if age_seconds is None:
        return "—"
    seconds = max(0, int(age_seconds))
    if seconds < 90:
        return "ahora"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        hours = max(1, seconds // 3600)
        return f"{hours} h"
    days = max(1, seconds // 86400)
    return f"{days} d"


def freshness_layers(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Frescura por capa (mercado / macro / empresas), no una sola hora de captura."""
    data = data or {}
    raw = data.get("Freshness") or {}
    specs = (
        ("market", "Mercado"),
        ("macro", "Macro"),
        ("companies", "Empresas"),
    )
    layers = []
    for key, default_label in specs:
        item = dict(raw.get(key) or {})
        label = item.get("label") or default_label
        status = str(item.get("status") or "UNKNOWN").upper()
        age = item.get("age_seconds")
        as_of = item.get("as_of")
        age_label = format_age_label(age) if status != "MISSING" else "sin dato"
        if key == "macro" and as_of:
            obs = format_obs_date(str(as_of))
            if obs:
                age_label = f"{age_label} · obs. {obs}" if status != "MISSING" else f"obs. {obs}"
        layers.append({
            "id": key,
            "label": label,
            "age_seconds": age,
            "age_label": age_label,
            "status": status,
            "as_of": as_of,
        })
    if not raw and isinstance(data.get("_cache_age_seconds"), (int, float)):
        age = data["_cache_age_seconds"]
        layers = [{
            "id": "market",
            "label": "Mercado",
            "age_seconds": int(age),
            "age_label": format_age_label(age),
            "status": "STALE" if age > 120 else "OK",
        }]
    parts = [f"{layer['label']} {layer['age_label']}" for layer in layers]
    statuses = {layer["status"] for layer in layers}
    if "MISSING" in statuses or "ERROR" in statuses:
        tone = "bad"
    elif "STALE" in statuses:
        tone = "warn"
    else:
        tone = "good"
    return {
        "headline": " · ".join(parts) if parts else "Sin frescura por capa",
        "tone": tone,
        "layers": layers,
    }


_CONFIDENCE_RANK = {"BAJA": 0, "MEDIA": 1, "ALTA": 2}


def _downgrade_confidence(level: str) -> str:
    if level == "ALTA":
        return "MEDIA"
    return "BAJA"


def refine_stance_confidence(
    decision: Dict[str, Any] | None,
    data: Dict[str, Any] | None,
    calendar: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """La confianza de la postura baja si el dato es flojo o el calendario es estimado."""
    decision = decision or {}
    data = data or {}
    calendar = calendar or {}
    level = str(decision.get("confidence") or "MEDIA").upper()
    if level not in _CONFIDENCE_RANK:
        level = "MEDIA"
    reasons: List[str] = []

    freshness = freshness_layers(data)
    market = next((layer for layer in freshness["layers"] if layer["id"] == "market"), None)
    macro = next((layer for layer in freshness["layers"] if layer["id"] == "macro"), None)
    if market and market["status"] in {"ERROR", "MISSING"}:
        level = "BAJA"
        reasons.append("faltan datos de mercado")
    elif market and market["status"] == "STALE":
        level = _downgrade_confidence(level)
        reasons.append("mercado servido desde caché caducada")
    if macro and macro["status"] == "STALE" and _CONFIDENCE_RANK[level] > 0:
        if level == "ALTA":
            level = "MEDIA"
            reasons.append("macro caducada")

    quality = data.get("DataQuality") or {}
    core_keys = [key for key in quality if key == "VIX" or key.startswith("Assets.SPY") or key.startswith("Assets.QQQ")]
    core_status = [str((quality.get(key) or {}).get("status") or "").upper() for key in core_keys]
    if any(status in {"ERROR", "MISSING"} for status in core_status):
        level = "BAJA"
        if "faltan datos de mercado" not in reasons:
            reasons.append("VIX o índices incompletos")

    blocked = bool(calendar.get("should_block") or calendar.get("should_block_signals"))
    cal_conf = str(calendar.get("confidence") or "").upper()
    if blocked and cal_conf not in {"HIGH", "ALTA"}:
        level = _downgrade_confidence(level)
        reasons.append("calendario estimado, no oficial")
    if blocked and str(calendar.get("time_quality") or "") == "aproximada":
        if "calendario estimado, no oficial" not in reasons:
            reasons.append("ventana de calendario aproximada")

    if any("saneamiento" in str((item or {}).get("detail") or "") for item in quality.values()):
        level = "BAJA"
        reasons.append("lectura rechazada por cruce de fuentes")

    if decision.get("missing_inputs"):
        level = "BAJA"
        reasons.append("inputs críticos incompletos")

    unique = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    note = ("Bajada: " + " · ".join(unique[:3])) if unique else "Convicción según score y datos completos."
    return {"level": level, "reasons": unique[:3], "note": note}


def apply_stance_confidence(decision: Any, data: Dict[str, Any] | None, calendar: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = decision.to_dict() if hasattr(decision, "to_dict") else dict(decision or {})
    refined = refine_stance_confidence(payload, data, calendar)
    if hasattr(decision, "confidence"):
        decision.confidence = refined["level"]
        decision.confidence_note = refined["note"]
        decision.confidence_reasons = refined["reasons"]
    elif isinstance(decision, dict):
        decision["confidence"] = refined["level"]
        decision["confidence_note"] = refined["note"]
        decision["confidence_reasons"] = refined["reasons"]
    return refined


def compact_score_drivers(decision: Dict[str, Any] | None) -> List[Dict[str, str]]:
    """Agrupa las reglas que movieron el score; no inventa pesos."""
    grouped: Dict[str, List[str]] = {}
    order: List[str] = []
    for item in (decision or {}).get("score_breakdown") or []:
        factor = str(item.get("factor") or "Otros")
        reason = str(item.get("reason") or "").strip()
        if factor not in grouped:
            order.append(factor)
            grouped[factor] = []
        if reason and reason not in grouped[factor]:
            grouped[factor].append(reason)
    return [
        {"factor": factor, "detail": "; ".join(grouped[factor][:2])}
        for factor in order
        if grouped[factor]
    ]


def track_record_thesis(track: Dict[str, Any] | None) -> Dict[str, Any]:
    """Contrasta la tesis COMPRAR con el SPY a N días. No es PnL de cartera."""
    track = track or {}
    sample = int(track.get("sample_size") or 0)
    days = int(track.get("forward_days") or 5)
    if sample <= 0:
        return {
            "ready": False,
            "tone": "neutral",
            "headline": "Aún no hay muestra para contrastar la tesis",
            "detail": track.get("message") or "Se rellenará tras varias capturas persistidas.",
            "sample_size": 0,
            "forward_days": days,
        }
    count = int(track.get("macro_buy_count") or 0)
    hit = track.get("macro_buy_hit_rate_pct")
    avg = track.get("macro_buy_avg_return_pct")
    if count <= 0:
        return {
            "ready": True,
            "tone": "neutral",
            "headline": f"Sin COMPRAR en {sample} lecturas a {days}d",
            "detail": "No hay muestra de entradas para contrastar contra el S&P 500.",
            "sample_size": sample,
            "buy_count": 0,
            "forward_days": days,
        }
    hit_txt = f"{hit:.0f}%" if isinstance(hit, (int, float)) else "—"
    avg_txt = f"{avg:+.1f}%" if isinstance(avg, (int, float)) else "—"
    count20 = int(track.get("macro_buy_count_20d") or 0)
    hit20 = track.get("macro_buy_hit_rate_20d_pct")
    beats = isinstance(hit, (int, float)) and hit >= 50
    if beats:
        headline = f"COMPRAR acertó el sentido de SPY a {days}d en {hit_txt} de {count} casos"
        tone = "good"
    else:
        headline = f"COMPRAR no se confirmó a {days}d: SPY subió solo el {hit_txt} de {count} casos"
        tone = "warn"
    detail = f"Retorno medio de SPY tras esas señales: {avg_txt}."
    if count20 > 0 and isinstance(hit20, (int, float)):
        detail += f" A 20d: acierto {hit20:.0f}% en {count20} casos."
    detail += " No es la rentabilidad de una cartera NEXUS."
    return {
        "ready": True,
        "tone": tone,
        "headline": headline,
        "detail": detail,
        "sample_size": sample,
        "buy_count": count,
        "hit_rate_pct": hit,
        "avg_return_pct": avg,
        "forward_days": days,
        "beats_spy": beats,
        "buy_count_20d": count20,
        "hit_rate_20d_pct": hit20,
    }


_FLOW_BUCKET_LABELS = {
    "recibiendo": "Recibiendo flujo",
    "neutrales": "Neutrales",
    "perdiendo": "Perdiendo fuerza",
    "sin_datos": "Sin datos",
}


def rotation_flow_bucket(signal: str | None) -> str:
    """Misma clasificación que el mapa de rotación en la UI nativa."""
    text = str(signal or "").lower()
    if "entrada" in text or "mejora" in text:
        return "recibiendo"
    if "corrección" in text or "descanso" in text:
        return "perdiendo"
    if not text.strip() or "sin datos" in text:
        return "sin_datos"
    return "neutrales"


def compact_rotation_themes(rotation: Any) -> List[Dict[str, Any]]:
    """Versión persistible de los temas: ticker, señal y score."""
    if rotation is None:
        return []
    if hasattr(rotation, "themes"):
        themes = rotation.themes or []
    elif isinstance(rotation, dict):
        themes = rotation.get("themes") or []
    elif isinstance(rotation, list):
        themes = rotation
    else:
        return []

    compact: List[Dict[str, Any]] = []
    for theme in themes:
        if hasattr(theme, "ticker"):
            compact.append({
                "ticker": theme.ticker,
                "theme": theme.theme,
                "group": theme.group,
                "signal": theme.signal,
                "score": theme.score,
            })
        elif isinstance(theme, dict):
            compact.append({
                "ticker": theme.get("ticker"),
                "theme": theme.get("theme"),
                "group": theme.get("group"),
                "signal": theme.get("signal"),
                "score": theme.get("score"),
            })
    return compact


def prior_history_row(rows: List[Dict[str, Any]] | None, *, exported: bool) -> Dict[str, Any] | None:
    """Última evaluación anterior a la lectura actual.

    Si el snapshot se acaba de persistir, el último row *es* el actual.
    """
    if not rows:
        return None
    if exported:
        return rows[-2] if len(rows) >= 2 else None
    return rows[-1]


def _as_number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _signed(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:+.{digits}f}"


def operational_allows_entry(decision: Dict[str, Any] | None, calendar: Dict[str, Any] | None = None) -> bool:
    decision = decision or {}
    calendar = calendar or {}
    if decision.get("operational_pause_reason"):
        return False
    if calendar.get("should_block") or calendar.get("should_block_signals"):
        return False
    action = str(decision.get("operational_action") or decision.get("action") or "").upper()
    return "COMPRAR" in action


def rotation_operational_alignment(
    decision: Dict[str, Any] | None,
    rotation: Any,
    calendar: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Avisa cuando Rotación muestra receptores de flujo pero la operativa no autoriza entradas."""
    decision = decision or {}
    calendar = calendar or {}
    operational = decision.get("operational_action") or decision.get("action") or "—"
    pause = decision.get("operational_pause_reason")
    blocked = bool(calendar.get("should_block") or calendar.get("should_block_signals"))
    receiving = [
        theme for theme in compact_rotation_themes(rotation)
        if rotation_flow_bucket(theme.get("signal")) == "recibiendo"
    ]
    allows_entry = operational_allows_entry(decision, calendar)
    conflict = (not allows_entry) and bool(receiving)
    if conflict:
        reason = pause or ("bloqueo de calendario" if blocked else None)
        if reason:
            detail = (
                f"Resumen está en {operational} ({reason}). "
                f"Los {len(receiving)} temas en «recibiendo flujo» son vigilancia, no permiso de entrada."
            )
        else:
            detail = (
                f"La acción operativa es {operational}. "
                f"Los {len(receiving)} temas en «recibiendo flujo» no equivalen a una orden de compra."
            )
        return {
            "conflict": True,
            "severity": "warn",
            "stance": "surveillance",
            "title": "La operativa no autoriza entradas",
            "detail": detail,
            "operational_action": operational,
            "pause_reason": pause,
            "receiving_count": len(receiving),
        }
    return {
        "conflict": False,
        "severity": None,
        "stance": "aligned" if allows_entry else "idle",
        "title": None,
        "detail": None,
        "operational_action": operational,
        "pause_reason": pause,
        "receiving_count": len(receiving),
    }


def fx_gold_operational_alignment(
    decision: Dict[str, Any] | None,
    calendar: Dict[str, Any] | None = None,
    forex_signal: Dict[str, Any] | None = None,
    gold_signal: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Avisa cuando el sesgo FX/oro parece una entrada pero la operativa está pausada."""
    decision = decision or {}
    calendar = calendar or {}
    forex_signal = forex_signal or {}
    gold_signal = gold_signal or {}
    operational = decision.get("operational_action") or decision.get("action") or "—"
    pause = decision.get("operational_pause_reason")
    blocked = bool(calendar.get("should_block") or calendar.get("should_block_signals"))
    allows_entry = operational_allows_entry(decision, calendar)

    fx_action = str(forex_signal.get("action") or "").upper()
    gold_bias = str(gold_signal.get("bias") or "").upper()
    rel = forex_signal.get("rel_1m")
    directional = (
        "COMPRAR" in fx_action
        or "SESGO" in fx_action
        or gold_bias == "REFUGIO"
        or (isinstance(rel, (int, float)) and abs(float(rel)) >= 0.5)
    )
    conflict = (not allows_entry) and directional
    if conflict:
        reason = pause or ("bloqueo de calendario" if blocked else None)
        if reason:
            detail = (
                f"Resumen está en {operational} ({reason}). "
                "El sesgo de EUR/USD y oro es vigilancia, no permiso de entrada."
            )
        else:
            detail = (
                f"La acción operativa es {operational}. "
                "El sesgo de EUR/USD y oro no equivale a una orden de compra."
            )
        return {
            "conflict": True,
            "severity": "warn",
            "stance": "surveillance",
            "title": "La operativa no autoriza entradas",
            "detail": detail,
            "operational_action": operational,
            "pause_reason": pause,
        }
    return {
        "conflict": False,
        "severity": None,
        "stance": "aligned" if allows_entry else "idle",
        "title": None,
        "detail": None,
        "operational_action": operational,
        "pause_reason": pause,
    }


def build_fx_gold_plan(
    decision: Dict[str, Any] | None,
    calendar: Dict[str, Any] | None,
    forex_signal: Dict[str, Any] | None,
    gold_signal: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Veredicto corto: COMPRAR / ESPERAR / VENDER y qué instrumento comprar."""
    decision = decision or {}
    calendar = calendar or {}
    forex_signal = forex_signal or {}
    gold_signal = gold_signal or {}
    allows_entry = operational_allows_entry(decision, calendar)
    pause = decision.get("operational_pause_reason")
    blocked = bool(calendar.get("should_block") or calendar.get("should_block_signals"))
    operational = decision.get("operational_action") or decision.get("action") or "—"
    fx_action = str(forex_signal.get("action") or "").upper()
    gold_bias = str(gold_signal.get("bias") or "").upper()

    if "COMPRAR EURO" in fx_action:
        tech_stance, tech_buy, tech_sell = "COMPRAR", "EURO frente al dólar", "Dólar"
        tech_doing = "Favorecer el euro frente al dólar solo si la operativa lo autoriza y el cruce de medias se mantiene."
    elif "COMPRAR DOLAR" in fx_action:
        tech_stance, tech_buy, tech_sell = "COMPRAR", "DÓLAR frente al euro", "Euro"
        tech_doing = "Favorecer el dólar frente al euro; vender o no comprar EUR/USD mientras el sesgo se sostenga."
    elif "SESGO EURO" in fx_action:
        tech_stance, tech_buy, tech_sell = "ESPERAR", "Nada ahora", "No forzar el euro"
        tech_doing = "Hay sesgo hacia el euro, pero no es entrada. Mantener si ya hay exposición; no abrir ahora."
    elif "SESGO DOLAR" in fx_action:
        tech_stance, tech_buy, tech_sell = "ESPERAR", "Nada ahora", "No forzar el dólar"
        tech_doing = "Hay sesgo hacia el dólar, pero no es entrada. No comprar euro; esperar confirmación."
    else:
        tech_stance, tech_buy, tech_sell = "ESPERAR", "Nada ahora", "EUR y USD"
        tech_doing = "Sin ventaja clara en el par. Esperar una ruptura de medias o del relativo 1M."

    gold_line = None
    if gold_bias == "REFUGIO":
        gold_line = "El oro está en REFUGIO: vigilancia, no sustituye al veredicto del par."
    elif gold_bias == "PRESION":
        gold_line = "El oro está en PRESIÓN: no perseguir GLD."

    if not allows_entry:
        reason = pause or ("bloqueo de calendario" if blocked else operational)
        stance, buy = "ESPERAR", "Nada ahora"
        if tech_stance == "COMPRAR":
            verdict = (
                f"ESPERAR. El sesgo técnico apunta a {tech_buy}, "
                f"pero la operativa está en {operational} ({reason}). No comprar."
            )
        else:
            verdict = f"ESPERAR. No hay permiso operativo ({reason}). No comprar EUR, USD ni oro."
        doing = f"{tech_doing} Mientras Resumen no autorice, esto es vigilancia."
        sell = "Cualquier entrada nueva"
    else:
        stance, buy, sell = tech_stance, tech_buy, tech_sell
        if stance == "COMPRAR":
            verdict = f"COMPRAR {buy}. No comprar {sell.lower()}."
        else:
            verdict = "ESPERAR. No comprar nada en el par hasta que el sesgo se confirme."
        doing = tech_doing

    if gold_line:
        verdict = f"{verdict} {gold_line}"

    return {
        "stance": stance,
        "buy": buy,
        "sell": sell,
        "verdict": verdict,
        "doing": doing,
        "avoiding": "No operar por un dato aislado de momentum ni contradecir el bloqueo de Resumen. Confirmar con MA20/50 y el relativo 1M/3M.",
        "changes": "Un cruce sostenido de medias, un giro del relativo 1M o que Resumen autorice entradas cambiarían el veredicto.",
        "allows_entry": allows_entry,
    }


_SESSION_ASSET_LABELS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "TLT": "Bonos largos",
    "GLD": "Oro",
    "UUP": "Dólar",
    "EURUSD": "Euro / dólar",
    "CASH": "Liquidez",
}


def _fx_bias_line(forex_signal: Dict[str, Any] | None) -> str | None:
    action = str((forex_signal or {}).get("action") or "").upper()
    if "COMPRAR EURO" in action:
        return "Comprar euro / vender dólar"
    if "COMPRAR DOLAR" in action:
        return "Comprar dólar / vender euro"
    if "SESGO EURO" in action:
        return "Sesgo a euro, sin entrada en el par"
    if "SESGO DOLAR" in action:
        return "Sesgo a dólar, sin entrada en el par"
    return None


def _gold_bias_line(gold_signal: Dict[str, Any] | None) -> str:
    bias = str((gold_signal or {}).get("bias") or "").upper()
    if bias == "REFUGIO":
        return "REFUGIO · vigilancia"
    if bias == "PRESION":
        return "PRESIÓN · no perseguir"
    if bias == "MIXTO":
        return "MIXTO"
    return bias or "Sin dato"


def _risk_allocation_line(allocation: Dict[str, Any] | None) -> str | None:
    ranked = sorted(
        (
            (str(key).upper(), int(weight))
            for key, weight in (allocation or {}).items()
            if isinstance(weight, (int, float)) and weight > 0 and str(key).upper() != "CASH"
        ),
        key=lambda item: -item[1],
    )
    if not ranked:
        return None
    return " · ".join(
        f"{_SESSION_ASSET_LABELS.get(key, key)} {weight}%"
        for key, weight in ranked[:3]
    )


def _favored_bias_line(decision: Dict[str, Any]) -> str | None:
    favored = [
        str(item)
        for item in (decision.get("favored_assets") or [])
        if str(item).strip() and str(item).upper() not in {"CASH", "LIQUIDEZ"}
    ]
    return " · ".join(favored[:3]) if favored else None


def _weight(allocation: Dict[str, Any] | None, ticker: str) -> int:
    value = (allocation or {}).get(ticker)
    return int(value) if isinstance(value, (int, float)) and value > 0 else 0


def _session_legs(
    decision: Dict[str, Any],
    forex_signal: Dict[str, Any] | None,
    allows_entry: bool,
) -> List[Dict[str, Any]]:
    """Una fila por activo: qué hacer ahora y qué peso de cartera usaría el modelo."""
    operational = decision.get("allocation") or {}
    macro = decision.get("macro_allocation") or operational
    fx_line = _fx_bias_line(forex_signal)
    legs: List[Dict[str, Any]] = []

    if fx_line:
        buying_fx = allows_entry and fx_line.lower().startswith("comprar")
        legs.append({
            "ticker": "EURUSD",
            "label": "Euro / dólar",
            "verb": fx_line,
            "now": "COMPRAR" if buying_fx else "NO ABRIR",
            "now_weight": None,
            "open_weight": None,
            "weight_note": (
                "Sesgo del par, no es un porcentaje de cartera."
                if not buying_fx
                else "Orden del par: no usa peso de cartera."
            ),
            "kind": "fx",
        })

    order = ["SPY", "QQQ", "TLT", "GLD", "UUP", "CASH"]
    extra = [
        str(key).upper()
        for key in list(operational.keys()) + list(macro.keys())
        if str(key).upper() not in order
    ]
    for ticker in order + extra:
        now_w = _weight(operational, ticker)
        open_w = _weight(macro, ticker)
        if now_w <= 0 and open_w <= 0:
            continue
        label = _SESSION_ASSET_LABELS.get(ticker, ticker)
        if ticker == "CASH":
            now = "MANTENER"
            verb = "Liquidez"
            if allows_entry:
                note = f"{now_w or open_w}% de la cartera en liquidez."
            elif open_w and open_w != now_w:
                note = f"{now_w}% ahora · {open_w}% de cartera si se abre"
            else:
                note = f"{now_w or open_w}% de la cartera en liquidez."
        elif allows_entry and open_w > 0:
            now = "COMPRAR"
            verb = f"Comprar {label}"
            note = f"{open_w}% de la cartera"
        elif now_w > 0 and not allows_entry:
            now = "MANTENER"
            verb = f"Mantener {label} solo si ya está en cartera"
            note = (
                f"{now_w}% ahora por el bloqueo"
                + (f" · {open_w}% de cartera si se abre" if open_w else "")
            )
        else:
            now = "NO ABRIR"
            verb = f"Comprar {label} solo si se abre"
            note = f"0% ahora · {open_w}% de la cartera si se abre" if open_w else "Sin peso de cartera"
        legs.append({
            "ticker": ticker,
            "label": label,
            "verb": verb,
            "now": now,
            "now_weight": now_w or None,
            "open_weight": open_w or None,
            "weight_note": note,
            "kind": "cash" if ticker == "CASH" else "asset",
        })
    return legs


def build_session_plan(
    decision: Dict[str, Any] | None,
    calendar: Dict[str, Any] | None,
    forex_signal: Dict[str, Any] | None,
    gold_signal: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Veredicto de sesión: qué hacer, qué sesgo hay y si es orden o vigilancia."""
    decision = decision or {}
    calendar = calendar or {}
    allows_entry = operational_allows_entry(decision, calendar)
    pause = decision.get("operational_pause_reason")
    blocked = bool(calendar.get("should_block") or calendar.get("should_block_signals"))
    operational = str(decision.get("operational_action") or decision.get("action") or "ESPERAR")
    macro = str(decision.get("macro_action") or decision.get("action") or "—")
    reason = pause or ("bloqueo de calendario" if blocked else operational)

    fx_line = _fx_bias_line(forex_signal)
    gold_line = _gold_bias_line(gold_signal)
    risk_line = _risk_allocation_line(decision.get("macro_allocation") or decision.get("allocation"))
    favored_line = _favored_bias_line(decision)
    equity_bias = risk_line or favored_line
    legs = _session_legs(decision, forex_signal, allows_entry)

    upper = operational.upper()
    if "REDUCIR" in upper or "VENDER" in upper:
        stance = "REDUCIR"
    elif allows_entry and "COMPRAR" in upper:
        stance = "COMPRAR"
    else:
        stance = "ESPERAR"

    weight_caption = (
        "El porcentaje es el peso sobre 100 de cartera, no un precio ni un número de contratos. "
        "Euro/dólar es sesgo del par, no un %."
    )
    named = [
        f"{item['label']} {item['open_weight']}%"
        for item in legs
        if item.get("kind") == "asset" and item.get("open_weight")
    ]
    if stance == "COMPRAR":
        buy_label = "COMPRAR"
        buy_parts = [fx_line] if fx_line else []
        buy_parts.extend(named[:3] or ([equity_bias] if equity_bias else []))
        buy = " · ".join(part for part in buy_parts if part) or "Nada de riesgo. Liquidez."
        sell = "No forzar lo que no lidera la asignación"
        verdict = (
            f"COMPRAR. Destina la cartera así: {', '.join(named) or 'liquidez'}. "
            + (f"En el par: {fx_line}. " if fx_line else "")
            + "Los % son peso de cartera."
        )
        if gold_line.startswith("REFUGIO"):
            verdict = f"{verdict} El oro está en refugio: contexto, no el foco."
        elif gold_line.startswith("PRESIÓN"):
            verdict = f"{verdict} No perseguir oro."
        doing = (
            "Abrir o mantener lo de la tabla. "
            "Respeta esos pesos y el bloqueo si reaparece."
        )
        avoiding = "No comprar lo que la tabla deja en 0% ni contradecir un bloqueo de calendario."
        changes = "Un giro del score, del VIX o del par, o un evento de calendario, cambiarían el veredicto."
    elif stance == "REDUCIR":
        buy_label = "COMPRAR"
        buy = "Nada ahora"
        sell = "Riesgo: recortar, no añadir"
        verdict = (
            f"REDUCIR. Subir liquidez. No comprar S&P 500, Nasdaq ni el par "
            f"hasta que baje el estrés ({reason})."
        )
        if fx_line:
            verdict = f"{verdict} El sesgo FX ({fx_line}) es vigilancia, no una orden."
        doing = "Reducir exposición y esperar. El sesgo técnico no autoriza entradas nuevas."
        avoiding = "No cazar rebotes ni abrir EUR, USD u oro contra el filtro de riesgo."
        changes = "Que baje el estrés y la operativa pase a COMPRAR o ESPERAR sin bloqueo."
    else:
        buy_label = "AHORA"
        buy = "Nada ahora"
        sell = "Cualquier entrada nueva"
        open_line = ", ".join(named) if named else None
        if fx_line or open_line:
            verdict = (
                f"ESPERAR. No abrir S&P 500, Nasdaq ni el par. "
                f"Si se levantara el bloqueo, el modelo usaría "
                f"{open_line or 'la asignación macro'}"
                f"{f' y {fx_line.lower()}' if fx_line else ''}. "
                f"Hoy no: operativa en {operational} ({reason})."
            )
        else:
            verdict = f"ESPERAR. No hay permiso operativo ({reason}). No abrir riesgo."
        doing = (
            "Vigilancia. Mantener la liquidez de la tabla. "
            "Los % de «si se abre» no son una orden de hoy."
        )
        avoiding = "No interpretar el sesgo de divisas, oro o ranking como permiso de compra."
        changes = "Que se levante el bloqueo y la reevaluación mantenga el sesgo convertiría esto en una orden."

    block_value = "Libre"
    if blocked:
        hours = calendar.get("block_hours")
        block_value = f"Activo · {hours}h" if hours is not None else "Activo"
    elif pause:
        block_value = str(pause)

    context = [
        {"label": "MACRO", "value": macro},
        {"label": "FX", "value": fx_line or "Sin ventaja en el par"},
        {"label": "ORO", "value": gold_line},
        {"label": "BLOQUEO", "value": block_value},
    ]

    drivers = compact_score_drivers(decision)
    confidence = str(decision.get("confidence") or "MEDIA")
    confidence_note = decision.get("confidence_note")

    return {
        "stance": stance,
        "buy": buy,
        "buy_label": buy_label,
        "sell": sell,
        "verdict": verdict,
        "doing": doing,
        "avoiding": avoiding,
        "changes": changes,
        "allows_entry": allows_entry,
        "weight_caption": weight_caption,
        "legs": legs,
        "context": context,
        "score": decision.get("score"),
        "confidence": confidence,
        "confidence_note": confidence_note,
        "score_drivers": drivers,
    }


def build_session_digest(
    current: Dict[str, Any],
    prior: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Resumen de lo que cambió vs la última evaluación persistida."""
    empty_metric = {"from": None, "to": None, "delta": None, "changed": False}
    if not prior:
        return {
            "has_prior": False,
            "baseline_captured_at": None,
            "headline": "Aún no hay una evaluación anterior",
            "summary": "Este bloque se rellenará tras la próxima captura persistida.",
            "action": {"from": None, "to": current.get("operational_action"), "changed": False},
            "score": {**empty_metric, "to": _as_number(current.get("score"))},
            "vix": {**empty_metric, "to": _as_number(current.get("vix"))},
            "rotation_crossings": [],
            "rotation_note": None,
        }

    current_action = current.get("operational_action") or current.get("action")
    prior_action = prior.get("operational_action") or prior.get("action")
    current_score = _as_number(current.get("score"))
    prior_score = _as_number(prior.get("score"))
    current_vix = _as_number(current.get("vix"))
    prior_vix = _as_number(prior.get("vix"))
    score_delta = round(current_score - prior_score, 1) if current_score is not None and prior_score is not None else None
    vix_delta = round(current_vix - prior_vix, 1) if current_vix is not None and prior_vix is not None else None
    action_changed = current_action != prior_action

    current_themes = compact_rotation_themes(current.get("rotation_themes") or current.get("rotation"))
    prior_themes = compact_rotation_themes(prior.get("rotation_themes") or prior.get("rotation"))
    prior_by_ticker = {
        str(theme.get("ticker")): theme
        for theme in prior_themes
        if theme.get("ticker")
    }
    crossings: List[Dict[str, Any]] = []
    if prior_themes:
        for theme in current_themes:
            ticker = theme.get("ticker")
            if not ticker or ticker not in prior_by_ticker:
                continue
            from_bucket = rotation_flow_bucket(prior_by_ticker[ticker].get("signal"))
            to_bucket = rotation_flow_bucket(theme.get("signal"))
            if from_bucket == to_bucket:
                continue
            crossings.append({
                "ticker": ticker,
                "theme": theme.get("theme") or ticker,
                "group": theme.get("group"),
                "from_bucket": from_bucket,
                "to_bucket": to_bucket,
                "from_label": _FLOW_BUCKET_LABELS[from_bucket],
                "to_label": _FLOW_BUCKET_LABELS[to_bucket],
            })
        crossings.sort(
            key=lambda item: (
                0 if "recibiendo" in {item["from_bucket"], item["to_bucket"]} else 1,
                item.get("theme") or "",
            )
        )
        rotation_note = None
    else:
        rotation_note = "Los cruces de rotación aparecerán tras la próxima captura persistida."

    shown = crossings[:3]
    if action_changed:
        headline = f"La acción pasó de {prior_action} a {current_action}"
    elif crossings:
        count = len(crossings)
        noun = "tema" if count == 1 else "temas"
        headline = f"{count} {noun} cambiaron de columna"
    elif score_delta not in (None, 0) or vix_delta not in (None, 0):
        headline = "La acción se mantiene; se movieron score o VIX"
    else:
        headline = "Sin cambios relevantes desde la última evaluación"

    parts: List[str] = []
    if score_delta is not None:
        parts.append(f"Score {_signed(score_delta)}")
    if vix_delta is not None:
        parts.append(f"VIX {_signed(vix_delta)}")
    if shown:
        names = ", ".join(str(item.get("theme") or item.get("ticker")) for item in shown)
        parts.append(f"Rotación: {names}")
    elif rotation_note:
        parts.append(rotation_note)
    summary = " · ".join(parts) if parts else "Nada material respecto a la captura anterior."

    return {
        "has_prior": True,
        "baseline_captured_at": prior.get("captured_at"),
        "headline": headline,
        "summary": summary,
        "action": {"from": prior_action, "to": current_action, "changed": action_changed},
        "score": {
            "from": prior_score,
            "to": current_score,
            "delta": score_delta,
            "changed": score_delta not in (None, 0),
        },
        "vix": {
            "from": prior_vix,
            "to": current_vix,
            "delta": vix_delta,
            "changed": vix_delta not in (None, 0),
        },
        "rotation_crossings": shown,
        "rotation_note": rotation_note,
    }


EURUSD_PIP = 10000
EURUSD_MATERIAL_PIPS = 5.0
GLD_MATERIAL_USD = 0.80


def _history_price(row: Dict[str, Any] | None, ticker: str) -> float | None:
    if not row:
        return None
    prices = row.get("prices") or {}
    return _as_number(prices.get(ticker))


def _price_move(current: float | None, prior: float | None, *, digits: int = 4) -> Dict[str, Any]:
    delta = None
    if current is not None and prior is not None:
        delta = round(current - prior, digits)
    return {"from": prior, "to": current, "delta": delta, "changed": False}


def _pip_digits(pips: float | None) -> int:
    if pips is None:
        return 1
    return 0 if abs(pips - round(pips)) < 0.05 else 1


def _digest_move_label(delta: float | None, *, unit: str, digits: int) -> str:
    if delta is None:
        return "sin base previa"
    if abs(delta) < 10 ** (-digits):
        return "sin movimiento"
    return f"{_signed(delta, digits)}{unit}"


def build_fx_gold_digest(
    current: Dict[str, Any],
    prior: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Cambios de EUR/USD, GLD y sesgo vs la última evaluación persistida."""
    eurusd_to = _as_number(current.get("eurusd"))
    gld_to = _as_number(current.get("gld"))
    fx_to = current.get("forex_action")
    gold_to = current.get("gold_bias")
    empty_change = {"from": None, "to": None, "changed": False}

    if not prior:
        return {
            "has_prior": False,
            "baseline_captured_at": None,
            "headline": "Aún no hay una evaluación anterior",
            "summary": "Los deltas aparecerán tras la próxima captura persistida. Abajo está la lectura actual.",
            "forex_action": {**empty_change, "to": fx_to, "label": fx_to or "sin dato"},
            "gold_bias": {**empty_change, "to": gold_to, "label": gold_to or "sin dato"},
            "eurusd": {
                **_price_move(eurusd_to, None),
                "pips": None,
                "label": "sin base previa",
            },
            "gld": {**_price_move(gld_to, None, digits=2), "label": "sin base previa"},
        }

    eurusd = _price_move(eurusd_to, _history_price(prior, "EURUSD"), digits=5)
    pips = round(eurusd["delta"] * EURUSD_PIP, 1) if eurusd["delta"] is not None else None
    eurusd["pips"] = pips
    eurusd["changed"] = pips is not None and abs(pips) >= EURUSD_MATERIAL_PIPS

    gld = _price_move(gld_to, _history_price(prior, "GLD"), digits=2)
    gld["changed"] = gld["delta"] is not None and abs(gld["delta"]) >= GLD_MATERIAL_USD

    fx_from = prior.get("forex_action")
    gold_from = prior.get("gold_bias")
    fx_changed = fx_from is not None and fx_to is not None and fx_from != fx_to
    gold_changed = gold_from is not None and gold_to is not None and gold_from != gold_to

    eurusd["label"] = _digest_move_label(pips, unit=" pips", digits=_pip_digits(pips))
    gld["label"] = _digest_move_label(gld["delta"], unit="", digits=2)

    fx_label = fx_to or "sin dato"
    if fx_changed:
        fx_label = f"{fx_from} → {fx_to}"
    elif fx_from is None:
        fx_label = fx_to or "sin dato anterior"

    gold_label = gold_to or "sin dato"
    if gold_changed:
        gold_label = f"{gold_from} → {gold_to}"
    elif gold_from is None:
        gold_label = gold_to or "sin dato anterior"

    if fx_changed:
        headline = f"La señal FX pasó de {fx_from} a {fx_to}"
    elif gold_changed:
        headline = f"El oro pasó de {gold_from} a {gold_to}"
    elif eurusd["changed"]:
        headline = f"EUR/USD {_signed(pips, _pip_digits(pips))} pips"
    elif gld["changed"]:
        headline = f"GLD {_signed(gld['delta'], 2)}"
    else:
        headline = "Sin cambios relevantes en divisas y oro"

    parts: List[str] = []
    if pips is not None:
        parts.append(f"EUR/USD {_signed(pips, _pip_digits(pips))} pips")
    if gld["delta"] is not None:
        parts.append(f"GLD {_signed(gld['delta'], 2)}")
    if fx_changed:
        parts.append(f"Señal FX: {fx_from} → {fx_to}")
    elif fx_from is None:
        parts.append("La señal FX se comparará tras la próxima captura persistida.")
    if gold_changed:
        parts.append(f"Sesgo oro: {gold_from} → {gold_to}")
    elif gold_from is None:
        parts.append("El sesgo de oro se comparará tras la próxima captura persistida.")
    summary = " · ".join(parts) if parts else "Nada material respecto a la captura anterior."

    return {
        "has_prior": True,
        "baseline_captured_at": prior.get("captured_at"),
        "headline": headline,
        "summary": summary,
        "forex_action": {"from": fx_from, "to": fx_to, "changed": fx_changed, "label": fx_label},
        "gold_bias": {"from": gold_from, "to": gold_to, "changed": gold_changed, "label": gold_label},
        "eurusd": eurusd,
        "gld": gld,
    }
