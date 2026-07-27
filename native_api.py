"""
Payload JSON para la app nativa SwiftUI (NEXUS Native).

Reutiliza el motor Python y expone un contrato estable vía FastAPI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from decision_intelligence import (
    classify_market_regime,
    data_quality_summary,
    detect_market_anomalies,
    score_attribution,
)
from forex_engine import forex_bidirectional_rates, forex_dual_perspective, forex_signal
from history_view import (
    compare_to_prior,
    filter_history_period,
    load_history_jsonl,
    load_history_period,
    summarize_history,
)
from paper_trading import summarize_paper_trading
from risk_filters.calendar import build_calendar_context, check_macro_events
from risk_filters.sentiment import aggregate_news_narratives, analyze_news_items
from signal_track_record import evaluate_track_record
from utils import build_snapshot, snapshot_signature


def _seconds_until(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None
    try:
        target = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return max(0, int((target - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return None


def _block_banner(calendar: Dict[str, Any], status: str, decision: Dict[str, Any]) -> Dict[str, Any] | None:
    """Banner accionable cuando hay bloqueo / pausa operativa."""
    should_block = bool(calendar.get("should_block_signals") or calendar.get("should_block"))
    pause = decision.get("operational_pause_reason")
    next_event = calendar.get("next_event") or {}
    if not should_block and not pause and str(status).upper() != "BLOCKED":
        return None

    event_title = next_event.get("title") or "Evento macro"
    event_when = (
        next_event.get("when_utc")
        or next_event.get("date")
        or next_event.get("datetime")
        or next_event.get("when")
    )
    hours = calendar.get("block_hours")
    secs = _seconds_until(event_when)
    if secs is None and isinstance(next_event.get("hours_until"), (int, float)):
        secs = max(0, int(float(next_event["hours_until"]) * 3600))
    guidance = pause or "No abrir posiciones nuevas hasta que levante el filtro de riesgo."
    if should_block:
        guidance = (
            f"Calendario activo ({hours}h). {guidance} "
            f"Espera al evento «{event_title}» y reevalúa."
        )
    return {
        "severity": "BLOCK",
        "title": "Riesgo activo — no forzar entradas",
        "guidance": guidance,
        "status": status,
        "block_hours": hours,
        "event_title": event_title,
        "event_at": event_when,
        "countdown_seconds": secs,
        "action_hint": decision.get("operational_action") or decision.get("action"),
    }


def _status_chip(status: str, calendar: Dict[str, Any]) -> Dict[str, Any]:
    """Chip único: estado motor + macro si aplica."""
    should_block = bool(calendar.get("should_block_signals") or calendar.get("should_block"))
    hours = calendar.get("block_hours")
    label = str(status or "—")
    if should_block and hours:
        label = f"{status} · Bloqueo {hours}h"
    elif should_block:
        label = f"{status} · Macro"
    tone = "neutral"
    upper = str(status).upper()
    if upper == "HEALTHY" and not should_block:
        tone = "good"
    elif upper in {"BLOCKED", "PANIC"} or should_block:
        tone = "bad"
    elif upper == "CAUTION":
        tone = "warn"
    return {"label": label, "tone": tone, "status": status, "macro_block": should_block}


def build_native_snapshot(*, export: bool = False) -> Dict[str, Any]:
    raw = build_snapshot(use_news=True, export=export)
    data = raw["data"]
    decision = raw["decision_dict"]
    news_items = raw.get("news_items") or []
    calendar = check_macro_events()
    sentiment = analyze_news_items(news_items)

    fx = (data.get("Forex") or {}).get("EURUSD") or {}
    uup = (data.get("Assets") or {}).get("UUP") or {}
    gld = (data.get("Assets") or {}).get("GLD") or {}
    fx_sig = forex_signal(fx, uup, news_items)
    dual = forex_dual_perspective(fx_sig)
    rates = forex_bidirectional_rates(fx)

    history_rows = load_history_jsonl(limit=120)
    history = summarize_history(limit=120)
    comparison = compare_to_prior(history_rows)
    period_rows = load_history_period("90d")
    history_periods = {
        period: summarize_history(
            period=period,
            max_points=120,
            rows=filter_history_period(period_rows, period),
        )
        for period in ("7d", "30d", "90d")
    }

    sources = sorted({str(item.get("source") or "RSS") for item in news_items})
    return {
        "schema": "nexus.native.v1",
        "captured_at_utc": raw.get("captured_at_utc"),
        "audit": {
            "snapshot_hash": snapshot_signature(raw),
            "exported": export,
            "captured_at_utc": raw.get("captured_at_utc"),
            "cache_age_seconds": data.get("_cache_age_seconds"),
        },
        "status": raw.get("status_value"),
        "alerts": (raw.get("alerts") or [])[:16],
        "status_chip": _status_chip(str(raw.get("status_value")), calendar),
        "block_banner": _block_banner(calendar, str(raw.get("status_value")), decision),
        "decision": decision,
        "intelligence": {
            "regime": classify_market_regime(data),
            "score_attribution": score_attribution(data, decision),
            "anomalies": detect_market_anomalies(data),
            "data_quality": data_quality_summary(data),
        },
        "rotation": raw.get("rotation_dict"),
        "calendar": {
            "should_block": bool(calendar.get("should_block_signals")),
            "block_hours": calendar.get("block_hours"),
            "next_event": calendar.get("next_event"),
            "confidence": calendar.get("confidence"),
            "source": calendar.get("source"),
            "upcoming": (calendar.get("events_detail") or [])[:5],
            "context": build_calendar_context(calendar),
        },
        "market": {
            "VIX": data.get("VIX"),
            "VIX_MA5": data.get("VIX_MA5"),
            "VIX_MA10": data.get("VIX_MA10"),
            "VIX_MA20": data.get("VIX_MA20"),
            "US10Y": data.get("US10Y"),
            "US2Y": data.get("US2Y"),
            "Yield_Curve_Spread": data.get("Yield_Curve_Spread"),
            "CPI_YoY_Pct": data.get("CPI_YoY_Pct"),
            "Correlation_Proxy": data.get("Correlation_Proxy"),
            "M2_Change_Pct": data.get("M2_Change_Pct"),
            "China_M2_YoY_Pct": data.get("China_M2_YoY_Pct"),
            "PE_Forward": data.get("PE_Forward"),
            "PE_Forward_Percentile": data.get("PE_Forward_Percentile"),
            "PE_Trailing": data.get("PE_Trailing"),
        },
        "assets": data.get("Assets") or {},
        "global_markets": data.get("GlobalMarkets") or {},
        "forex": {
            "EURUSD": fx,
            "signal": fx_sig,
            "dual": dual,
            "rates": rates,
        },
        "gold": {
            "GLD": gld,
            "label": "Oro (GLD)",
        },
        "news": {
            "items": news_items[:40],
            "count": len(news_items),
            "sources": sources,
            "linkage": {
                "method": "explicit_keyword_heuristic",
                "causal": False,
                "note": "Las asociaciones son contextuales y no afirman impacto causal.",
            },
            "narratives": aggregate_news_narratives(news_items),
            "sentiment": {
                "dominant": sentiment.get("dominant_sentiment"),
                "details": sentiment.get("details"),
                "panic_score": sentiment.get("panic_score"),
            },
        },
        "history": history,
        "comparison": comparison,
        "history_periods": history_periods,
        "asset_ranking": comparison.get("asset_ranking", []),
        "change_attribution": comparison.get("attribution"),
        "paper": summarize_paper_trading(limit=40),
        "track_record": evaluate_track_record(forward_days=5, limit=80),
    }
