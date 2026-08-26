"""
Persistencia histórica de decisiones NEXUS.

Guarda snapshots auditables en JSONL y un resumen cómodo en CSV.
"""

import csv
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from config import DECISIONS_HISTORY_CSV, DECISIONS_HISTORY_JSONL, PAPER_PORTFOLIO_JSON

_HISTORY_IO_LOCK = threading.RLock()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _price_snapshot(data: Dict[str, Any]) -> Dict[str, float | None]:
    prices = {
        ticker: metrics.get("price")
        for ticker, metrics in data.get("Assets", {}).items()
    }
    eurusd = (data.get("Forex") or {}).get("EURUSD") or {}
    if isinstance(eurusd, dict):
        prices["EURUSD"] = eurusd.get("price")
    return prices


def build_decision_snapshot(
    data: Dict[str, Any],
    decision,
    news_items: List[Dict[str, Any]],
    market_status: str | None = None,
    rotation: Any = None,
) -> Dict[str, Any]:
    from decision_intelligence import compact_rotation_themes
    from forex_engine import forex_signal, gold_signal

    macro_allocation = decision.macro_allocation or decision.allocation
    vix = data.get("VIX")
    fx = (data.get("Forex") or {}).get("EURUSD") or {}
    uup = (data.get("Assets") or {}).get("UUP") or {}
    gld = (data.get("Assets") or {}).get("GLD") or {}
    fx_sig = forex_signal(fx, uup, news_items)
    gold_sig = gold_signal(
        gld,
        uup,
        vix=vix,
        us10y=data.get("US10Y"),
        cpi_yoy=data.get("CPI_YoY_Pct"),
    )
    return {
        "captured_at": _now_utc_iso(),
        "action": decision.operational_action,
        "macro_action": decision.macro_action,
        "operational_action": decision.operational_action,
        "operational_pause_reason": decision.operational_pause_reason,
        "market_status": market_status,
        "score": decision.score,
        "confidence": decision.confidence,
        "confidence_note": getattr(decision, "confidence_note", None),
        "favored_assets": decision.favored_assets,
        "allocation": decision.allocation,
        "macro_allocation": macro_allocation,
        "asset_scores": decision.asset_scores,
        "rationale": decision.rationale,
        "inputs_used": decision.inputs_used,
        "missing_inputs": decision.missing_inputs,
        "prices": _price_snapshot(data),
        "vix": float(vix) if isinstance(vix, (int, float)) else None,
        "rotation_themes": compact_rotation_themes(rotation),
        "forex_action": fx_sig.get("action"),
        "gold_bias": gold_sig.get("bias"),
        "data_quality": data.get("DataQuality", {}),
        "news_count": len(news_items),
        "news_sources": sorted({item.get("source", "RSS") for item in news_items}),
    }


def export_decision_snapshot(
    data: Dict[str, Any],
    decision,
    news_items: List[Dict[str, Any]],
    jsonl_path: Path = DECISIONS_HISTORY_JSONL,
    csv_path: Path = DECISIONS_HISTORY_CSV,
    market_status: str | None = None,
    rotation: Any = None,
) -> Dict[str, str]:
    snapshot = build_decision_snapshot(
        data, decision, news_items, market_status=market_status, rotation=rotation
    )

    row = {
        "captured_at": snapshot["captured_at"],
        "action": snapshot["operational_action"],
        "macro_action": snapshot["macro_action"],
        "operational_action": snapshot["operational_action"],
        "market_status": snapshot.get("market_status"),
        "score": snapshot["score"],
        "confidence": snapshot["confidence"],
        "favored_assets": ", ".join(snapshot["favored_assets"]),
        "allocation": json.dumps(snapshot["allocation"], ensure_ascii=False),
        "missing_inputs": ", ".join(snapshot["missing_inputs"]),
        "news_count": snapshot["news_count"],
        "spy_price": snapshot["prices"].get("SPY"),
        "qqq_price": snapshot["prices"].get("QQQ"),
    }
    with _HISTORY_IO_LOCK:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        exists = csv_path.exists()
        with csv_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    paper_result = None
    try:
        from paper_trading import update_paper_portfolio
        paper_result = update_paper_portfolio(decision, snapshot["prices"])
    except Exception as exc:
        logging.exception("No se pudo actualizar paper trading: %s", exc)

    result = {"jsonl": str(jsonl_path), "csv": str(csv_path)}
    if paper_result:
        result["paper"] = str(PAPER_PORTFOLIO_JSON)
    return result
