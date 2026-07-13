"""
Persistencia histórica de decisiones NEXUS.

Guarda snapshots auditables en JSONL y un resumen cómodo en CSV.
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from config import DECISIONS_HISTORY_CSV, DECISIONS_HISTORY_JSONL, PAPER_PORTFOLIO_JSON


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _price_snapshot(data: Dict[str, Any]) -> Dict[str, float | None]:
    return {
        ticker: metrics.get("price")
        for ticker, metrics in data.get("Assets", {}).items()
    }


def build_decision_snapshot(
    data: Dict[str, Any],
    decision,
    news_items: List[Dict[str, Any]],
    market_status: str | None = None,
) -> Dict[str, Any]:
    macro_allocation = decision.macro_allocation or decision.allocation
    return {
        "captured_at": _now_utc_iso(),
        "action": decision.operational_action,
        "macro_action": decision.macro_action,
        "operational_action": decision.operational_action,
        "operational_pause_reason": decision.operational_pause_reason,
        "market_status": market_status,
        "score": decision.score,
        "confidence": decision.confidence,
        "favored_assets": decision.favored_assets,
        "allocation": decision.allocation,
        "macro_allocation": macro_allocation,
        "asset_scores": decision.asset_scores,
        "rationale": decision.rationale,
        "inputs_used": decision.inputs_used,
        "missing_inputs": decision.missing_inputs,
        "prices": _price_snapshot(data),
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
) -> Dict[str, str]:
    snapshot = build_decision_snapshot(data, decision, news_items, market_status=market_status)

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
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
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)

    paper_result = None
    try:
        from paper_trading import update_paper_portfolio
        paper_result = update_paper_portfolio(decision, snapshot["prices"])
    except Exception:
        pass

    result = {"jsonl": str(jsonl_path), "csv": str(csv_path)}
    if paper_result:
        result["paper"] = str(PAPER_PORTFOLIO_JSON)
    return result
