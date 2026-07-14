"""
Paper trading / seguimiento de P&L virtual de señales NEXUS.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from config import PAPER_PORTFOLIO_JSON, PAPER_TRADES_JSONL


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_portfolio(path: Path = PAPER_PORTFOLIO_JSON) -> Dict[str, Any]:
    if not path.exists():
        return {
            "cash_pct": 100.0,
            "holdings": {},
            "entry_prices": {},
            "last_action": None,
            "last_score": None,
            "last_update": None,
            "starting_value": 100000.0,
            "current_value": 100000.0,
            "benchmark_spy_entry_price": None,
            "benchmark_start_value": 100000.0,
            "benchmark_current_value": 100000.0,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _save_portfolio(portfolio: Dict[str, Any], path: Path = PAPER_PORTFOLIO_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(portfolio, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_trade(record: Dict[str, Any], path: Path = PAPER_TRADES_JSONL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def update_paper_portfolio(
    decision,
    prices: Dict[str, float | None],
    path: Path = PAPER_PORTFOLIO_JSON,
) -> Dict[str, Any]:
    """
    Actualiza la cartera virtual según la asignación recomendada por NEXUS.
    """
    portfolio = _load_portfolio(path)
    allocation = decision.allocation
    total_value = float(portfolio.get("current_value", portfolio.get("starting_value", 100000.0)))

    new_holdings: Dict[str, float] = {}
    entry_prices = dict(portfolio.get("entry_prices", {}))
    pnl_by_asset: Dict[str, float] = {}

    for asset, weight in allocation.items():
        if asset == "CASH":
            continue
        price = prices.get(asset)
        if price is None or price <= 0:
            continue
        target_value = (weight / 100.0) * total_value
        shares = target_value / price
        new_holdings[asset] = shares
        previous_price = entry_prices.get(asset)
        if previous_price:
            pnl_by_asset[asset] = (price - previous_price) / previous_price * 100
        if asset not in entry_prices:
            entry_prices[asset] = price

    cash_weight = allocation.get("CASH", 0)
    new_holdings["CASH"] = (cash_weight / 100.0) * total_value

    marked_value = new_holdings.get("CASH", 0.0)
    for asset, shares in new_holdings.items():
        if asset == "CASH":
            continue
        price = prices.get(asset)
        if price is not None:
            marked_value += shares * price

    spy_price = prices.get("SPY")
    start_value = float(portfolio.get("starting_value", 100000.0))
    benchmark_entry = portfolio.get("benchmark_spy_entry_price")
    if benchmark_entry in (None, 0) and spy_price not in (None, 0):
        benchmark_entry = spy_price
        portfolio["benchmark_spy_entry_price"] = spy_price
        portfolio["benchmark_start_value"] = start_value
    benchmark_value = start_value
    if benchmark_entry not in (None, 0) and spy_price not in (None, 0):
        benchmark_value = (spy_price / benchmark_entry) * float(portfolio.get("benchmark_start_value", start_value))

    previous_action = portfolio.get("last_action")
    action_changed = previous_action != decision.action

    record = {
        "captured_at": _now_utc_iso(),
        "action": decision.action,
        "score": decision.score,
        "allocation": allocation,
        "prices": prices,
        "portfolio_value": round(marked_value, 2),
        "benchmark_value": round(benchmark_value, 2),
        "pnl_since_last_pct": round(((marked_value / total_value) - 1) * 100, 3) if total_value else 0.0,
        "pnl_by_asset_pct": pnl_by_asset,
        "action_changed": action_changed,
    }

    portfolio.update({
        "holdings": {k: round(v, 6) if k != "CASH" else round(v, 2) for k, v in new_holdings.items()},
        "entry_prices": entry_prices,
        "last_action": decision.action,
        "last_score": decision.score,
        "last_update": record["captured_at"],
        "current_value": round(marked_value, 2),
        "benchmark_current_value": round(benchmark_value, 2),
        "cash_pct": cash_weight,
    })

    _save_portfolio(portfolio, path)
    _append_trade(record)
    return {"portfolio": portfolio, "trade": record}


def summarize_paper_trading(limit: int = 20) -> Dict[str, Any]:
    portfolio = _load_portfolio()
    trades: List[Dict[str, Any]] = []
    if PAPER_TRADES_JSONL.exists():
        with PAPER_TRADES_JSONL.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        trades.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    if limit:
        trades = trades[-limit:]

    start = float(portfolio.get("starting_value", 100000.0))
    current = float(portfolio.get("current_value", start))
    benchmark_current = float(portfolio.get("benchmark_current_value", start))
    total_return = ((current / start) - 1) * 100 if start else 0.0
    benchmark_return = ((benchmark_current / start) - 1) * 100 if start else 0.0

    return {
        "portfolio": portfolio,
        "trades": trades,
        "total_return_pct": round(total_return, 2),
        "benchmark_return_pct": round(benchmark_return, 2),
        "alpha_vs_spy_pct": round(total_return - benchmark_return, 2),
        "trade_count": len(trades),
    }


def format_paper_report(limit: int = 10) -> str:
    summary = summarize_paper_trading(limit=limit)
    portfolio = summary["portfolio"]
    lines = [
        "PAPER TRADING NEXUS",
        f"Valor inicial: ${portfolio.get('starting_value', 0):,.2f}",
        f"Valor actual : ${portfolio.get('current_value', 0):,.2f}",
        f"Retorno total: {summary['total_return_pct']:+.2f}%",
        f"Buy&Hold SPY: {summary['benchmark_return_pct']:+.2f}%",
        f"Alpha vs SPY: {summary['alpha_vs_spy_pct']:+.2f}%",
        f"Última acción: {portfolio.get('last_action')} (score {portfolio.get('last_score')})",
        "",
        "POSICIÓN ACTUAL",
    ]
    for asset, amount in sorted(portfolio.get("holdings", {}).items()):
        if asset == "CASH":
            lines.append(f"  {asset:<8} ${amount:,.2f}")
        else:
            lines.append(f"  {asset:<8} {amount:.4f} uds @ {portfolio.get('entry_prices', {}).get(asset, '—')}")

    lines.extend(["", "ÚLTIMAS OPERACIONES"])
    if summary["trades"]:
        for trade in summary["trades"][-limit:]:
            lines.append(
                f"  {trade.get('captured_at')}  {trade.get('action')}  "
                f"valor=${trade.get('portfolio_value'):,.2f}  "
                f"Δ={trade.get('pnl_since_last_pct'):+.3f}%"
            )
    else:
        lines.append("  Sin operaciones registradas todavía.")

    return "\n".join(lines)
