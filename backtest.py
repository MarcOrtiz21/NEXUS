"""
Backtesting básico para NEXUS.

Reconstruye señales históricas con precios gratuitos de yfinance y compara
una cartera NEXUS contra buy-and-hold de SPY y QQQ.
"""

import argparse
import sys
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich import box

from data_ingestion import DECISION_ASSETS, SECTOR_ETFS, _calculate_asset_metrics, _calculate_sector_correlation
from decision_engine import DecisionEngine
from logic_engine import MarketStatus


console = Console()
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")
BACKTEST_TICKERS = sorted(set(["^VIX", "^TNX"] + DECISION_ASSETS + SECTOR_ETFS))


def _status_from_data(data: Dict[str, Any]) -> MarketStatus:
    vix = data.get("VIX")
    corr = data.get("Correlation_Proxy")
    if vix is not None and vix > 30:
        return MarketStatus.PANIC
    if (vix is not None and vix > 25) or (corr is not None and abs(corr) > 0.6):
        return MarketStatus.CAUTION
    return MarketStatus.HEALTHY


def _snapshot(df_close: pd.DataFrame, end_idx: int) -> Dict[str, Any]:
    hist = df_close.iloc[: end_idx + 1]
    row = df_close.iloc[end_idx]
    data = {
        "VIX": float(row["^VIX"]) if "^VIX" in row and pd.notna(row["^VIX"]) else None,
        "US10Y": float(row["^TNX"]) if "^TNX" in row and pd.notna(row["^TNX"]) else None,
        "Correlation_Proxy": _calculate_sector_correlation(hist, SECTOR_ETFS),
        "PE_Trailing": None,
        "PE_Forward": None,
        "M2_Change_Pct": None,
        "CPI_YoY_Pct": None,
        "Assets": {
            ticker: _calculate_asset_metrics(hist, ticker)
            for ticker in DECISION_ASSETS
        },
        "DataQuality": {},
    }
    return data


def _period_return(df_close: pd.DataFrame, start_idx: int, end_idx: int) -> Dict[str, float]:
    start = df_close.iloc[start_idx]
    end = df_close.iloc[end_idx]
    returns = {}
    for ticker in DECISION_ASSETS:
        if ticker in df_close.columns and pd.notna(start.get(ticker)) and pd.notna(end.get(ticker)) and start[ticker] > 0:
            returns[ticker] = float((end[ticker] / start[ticker]) - 1)
        else:
            returns[ticker] = 0.0
    returns["CASH"] = 0.0
    return returns


def _max_drawdown(values: List[float]) -> float:
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = (value / peak) - 1
        max_dd = min(max_dd, drawdown)
    return max_dd


def _annualized_volatility(values: List[float], periods_per_year: int) -> float:
    returns = pd.Series(values).pct_change().dropna()
    if returns.empty:
        return 0.0
    return float(returns.std() * np.sqrt(periods_per_year))


def _metrics(values: List[float], periods_per_year: int) -> Dict[str, float]:
    total_return = values[-1] / values[0] - 1
    return {
        "total_return": total_return,
        "volatility": _annualized_volatility(values, periods_per_year),
        "max_drawdown": _max_drawdown(values),
    }


def run_backtest(period: str = "5y", rebalance_days: int = 5) -> Dict[str, Any]:
    df = yf.download(BACKTEST_TICKERS, period=period, progress=False, auto_adjust=False)
    if df.empty or "Close" not in df.columns:
        raise RuntimeError("No se pudieron descargar datos históricos para el backtest.")

    df_close = df["Close"].dropna(how="all")
    start_idx = max(220, rebalance_days)
    if len(df_close) <= start_idx + rebalance_days:
        raise RuntimeError("Histórico insuficiente para reconstruir señales.")

    nexus_values = [1.0]
    spy_values = [1.0]
    qqq_values = [1.0]
    actions = []

    for idx in range(start_idx, len(df_close) - rebalance_days, rebalance_days):
        next_idx = idx + rebalance_days
        data = _snapshot(df_close, idx)
        status = _status_from_data(data)
        decision = DecisionEngine(data, status, []).evaluate()
        period_returns = _period_return(df_close, idx, next_idx)

        portfolio_return = sum(
            (weight / 100) * period_returns.get(asset, 0.0)
            for asset, weight in decision.allocation.items()
        )
        nexus_values.append(nexus_values[-1] * (1 + portfolio_return))
        spy_values.append(spy_values[-1] * (1 + period_returns.get("SPY", 0.0)))
        qqq_values.append(qqq_values[-1] * (1 + period_returns.get("QQQ", 0.0)))
        actions.append(decision.action)

    periods_per_year = round(252 / rebalance_days)
    return {
        "period": period,
        "rebalance_days": rebalance_days,
        "observations": len(actions),
        "nexus": _metrics(nexus_values, periods_per_year),
        "spy": _metrics(spy_values, periods_per_year),
        "qqq": _metrics(qqq_values, periods_per_year),
        "actions": {action: actions.count(action) for action in sorted(set(actions))},
    }


def _fmt_pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def render_report(result: Dict[str, Any]) -> None:
    table = Table(title=f"Backtest NEXUS ({result['period']}, rebalance {result['rebalance_days']}D)", box=box.SIMPLE_HEAVY)
    table.add_column("Estrategia", style="cyan")
    table.add_column("Retorno", justify="right")
    table.add_column("Volatilidad", justify="right")
    table.add_column("Max Drawdown", justify="right")

    for name, key in [("NEXUS", "nexus"), ("Buy & Hold SPY", "spy"), ("Buy & Hold QQQ", "qqq")]:
        metrics = result[key]
        table.add_row(
            name,
            _fmt_pct(metrics["total_return"]),
            _fmt_pct(metrics["volatility"]),
            _fmt_pct(metrics["max_drawdown"]),
        )

    console.print(table)
    action_summary = " | ".join(f"{action}: {count}" for action, count in result["actions"].items())
    console.print(f"[dim]Observaciones: {result['observations']} | Señales: {action_summary}[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtesting básico de NEXUS")
    parser.add_argument("--period", default="5y", help="Periodo yfinance, ej. 2y, 5y, 10y.")
    parser.add_argument("--rebalance-days", type=int, default=5, help="Frecuencia de rebalanceo en días de mercado.")
    args = parser.parse_args()

    result = run_backtest(period=args.period, rebalance_days=args.rebalance_days)
    render_report(result)


if __name__ == "__main__":
    main()
