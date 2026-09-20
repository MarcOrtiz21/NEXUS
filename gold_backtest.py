"""Backtest mensual point-in-time del motor explicable de oro."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf

from config import GOLD_BACKTEST_REPORT, REPORTS_DIR
from cftc_positioning import (
    fetch_gold_cot_history,
    positioning_data_fields,
    summarize_gold_positioning,
)
from fred_vintages import fetch_initial_releases, known_rows, lagged_change, latest_value
from gold_outlook import MODEL_VERSION, build_gold_outlook
from gold_validation import balanced_accuracy, brier_score, calibration_bins, walk_forward_splits


MONTHLY_SERIES = {
    "cpi": "CPIAUCSL",
    "core_cpi": "CPILFESL",
    "pce": "PCEPI",
    "core_pce": "PCEPILFE",
    "energy_cpi": "CPIENGSL",
    "unemployment": "UNRATE",
    "payrolls": "PAYEMS",
    "industrial": "INDPRO",
    "m2": "WM2NS",
}
DAILY_SERIES = {
    "real_yield": "DFII10",
    "breakeven": "T10YIE",
    "wti": "DCOILWTICO",
}
MARKET_TICKERS = ["GLD", "UUP", "^VIX"]


def _market_metrics(series: pd.Series) -> dict[str, float | None]:
    values = series.dropna().astype(float)
    if values.empty:
        return {"price": None, "ma20": None, "ma50": None, "ma200": None, "momentum_1m": None}
    result: dict[str, float | None] = {
        "price": float(values.iloc[-1]),
        "ma20": float(values.tail(20).mean()) if len(values) >= 20 else None,
        "ma50": float(values.tail(50).mean()) if len(values) >= 50 else None,
        "ma200": float(values.tail(200).mean()) if len(values) >= 200 else None,
        "momentum_1m": None,
    }
    if len(values) >= 22 and values.iloc[-22] > 0:
        result["momentum_1m"] = float((values.iloc[-1] / values.iloc[-22] - 1) * 100)
    return result


def _latest(rows: list[dict[str, Any]], cutoff: date) -> float | None:
    item = latest_value(rows, cutoff)
    return float(item["value"]) if item else None


def _macro_snapshot(series: dict[str, list[dict[str, Any]]], cutoff: date) -> dict[str, Any]:
    def change(name: str, periods: int, *, percent: bool = True) -> float | None:
        return lagged_change(series[name], cutoff, periods=periods, percent=percent)

    def annualized_three_month_change(name: str) -> float | None:
        change_pct = change(name, 3)
        if change_pct is None or change_pct <= -100:
            return None
        return round(((1 + change_pct / 100) ** 4 - 1) * 100, 4)

    data = {
        "CPI_MoM_Pct": change("cpi", 1),
        "CPI_3M_Annualized_Pct": annualized_three_month_change("cpi"),
        "CPI_YoY_Pct": change("cpi", 12),
        "Core_CPI_MoM_Pct": change("core_cpi", 1),
        "Core_CPI_3M_Annualized_Pct": annualized_three_month_change("core_cpi"),
        "Core_CPI_YoY_Pct": change("core_cpi", 12),
        "PCE_MoM_Pct": change("pce", 1),
        "PCE_3M_Annualized_Pct": annualized_three_month_change("pce"),
        "PCE_YoY_Pct": change("pce", 12),
        "Core_PCE_MoM_Pct": change("core_pce", 1),
        "Core_PCE_3M_Annualized_Pct": annualized_three_month_change("core_pce"),
        "Core_PCE_YoY_Pct": change("core_pce", 12),
        "Energy_CPI_MoM_Pct": change("energy_cpi", 1),
        "Energy_CPI_YoY_Pct": change("energy_cpi", 12),
        "Real_Yield_10Y_Pct": _latest(series["real_yield"], cutoff),
        "Real_Yield_10Y_1M_Change_Pp": change("real_yield", 21, percent=False),
        "Breakeven_10Y_Pct": _latest(series["breakeven"], cutoff),
        "Breakeven_10Y_1M_Change_Pp": change("breakeven", 21, percent=False),
        "WTI_Price": _latest(series["wti"], cutoff),
        "WTI_1M_Change_Pct": change("wti", 21),
        "Unemployment_Rate_Pct": _latest(series["unemployment"], cutoff),
        "Unemployment_1M_Change_Pp": change("unemployment", 1, percent=False),
        "Payrolls_1M_Change_Thousands": change("payrolls", 1, percent=False),
        "Industrial_Production_MoM_Pct": change("industrial", 1),
        "M2_Change_Pct": change("m2", 52),
    }
    releases = [
        row["release_at"] for rows in series.values() for row in known_rows(rows, cutoff)
    ]
    data["PointInTime_LastRelease"] = max(releases) if releases else None
    return data


def _decision_dates(index: pd.DatetimeIndex, start: date, end: date) -> list[pd.Timestamp]:
    available = pd.DatetimeIndex(index).tz_localize(None)
    selected: list[pd.Timestamp] = []
    for period in pd.period_range(start=start, end=end, freq="M"):
        candidates = available[(available.to_period("M") == period) & (available.day >= 15)]
        if len(candidates):
            selected.append(candidates[0])
    return selected


def _extract_close(download: pd.DataFrame, ticker: str) -> pd.Series:
    if isinstance(download.columns, pd.MultiIndex):
        for field in ("Adj Close", "Close"):
            if (field, ticker) in download.columns:
                return download[(field, ticker)]
    for field in ("Adj Close", "Close"):
        if field in download.columns and len(MARKET_TICKERS) == 1:
            return download[field]
    return pd.Series(dtype=float)


def download_market_history(start: date, end: date) -> pd.DataFrame:
    raw = yf.download(
        MARKET_TICKERS,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        progress=False,
        threads=True,
        timeout=30,
    )
    frame = pd.DataFrame({ticker: _extract_close(raw, ticker) for ticker in MARKET_TICKERS})
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None)
    return frame.sort_index()


def _evaluation(rows: list[dict[str, Any]], probability_key: str) -> dict[str, Any]:
    probabilities = [float(row[probability_key]) / 100 for row in rows]
    outcomes = [int(row["direction_up"]) for row in rows]
    return {
        "sample_size": len(rows),
        "brier_score": brier_score(probabilities, outcomes),
        "balanced_accuracy": balanced_accuracy(probabilities, outcomes),
        "mean_return_pct": round(sum(float(row["return_pct"]) for row in rows) / len(rows), 4) if rows else None,
        "calibration": calibration_bins(probabilities, outcomes),
    }


def _probability_without_group(groups: list[dict[str, Any]], horizon: str, omitted: str) -> float | None:
    signal_key = f"{horizon}_signal"
    weight_key = f"{horizon}_weight"
    available = [
        group for group in groups
        if group.get("id") != omitted and group.get(signal_key) is not None and float(group.get(weight_key) or 0) > 0
    ]
    weight = sum(float(group[weight_key]) for group in available)
    if not weight:
        return None
    raw = sum(float(group[signal_key]) * float(group[weight_key]) for group in available) / weight
    return round(max(15, min(85, 50 + raw * 35)), 2)


def _ablation_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    group_ids = sorted({key for row in rows for key in (row.get("ablation_probabilities") or {})})
    report: dict[str, Any] = {}
    for group_id in group_ids:
        comparable = [row for row in rows if (row.get("ablation_probabilities") or {}).get(group_id) is not None]
        if not comparable:
            continue
        prepared = [
            {**row, "ablation_probability": row["ablation_probabilities"][group_id]}
            for row in comparable
        ]
        metrics = _evaluation(prepared, "ablation_probability")
        comparable_full = _evaluation(comparable, "model_probability")
        brier = metrics.get("brier_score")
        full_brier = comparable_full.get("brier_score")
        accuracy = metrics.get("balanced_accuracy")
        full_accuracy = comparable_full.get("balanced_accuracy")
        delta_brier = round(brier - full_brier, 4) if brier is not None and full_brier is not None else None
        delta_accuracy = round(accuracy - full_accuracy, 4) if accuracy is not None and full_accuracy is not None else None
        if delta_brier is None or abs(delta_brier) < 0.002:
            interpretation = "NEUTRAL"
        elif delta_brier > 0:
            interpretation = "APORTA"
        else:
            interpretation = "REVISAR"
        report[group_id] = {
            **metrics,
            "delta_brier_vs_full": delta_brier,
            "delta_balanced_accuracy_vs_full": delta_accuracy,
            "interpretation": interpretation,
        }
    return report


def run_gold_backtest(
    *,
    start: date = date(2016, 1, 1),
    end: date | None = None,
    refresh: bool = False,
    report_path: Path = GOLD_BACKTEST_REPORT,
    market_prices: pd.DataFrame | None = None,
    vintage_series: dict[str, list[dict[str, Any]]] | None = None,
    cftc_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Ejecuta cortes mensuales desde la segunda quincena y guarda el informe."""
    end = end or datetime.now(timezone.utc).date()
    warmup = start - timedelta(days=800)
    series = vintage_series or {
        name: fetch_initial_releases(series_id, warmup.isoformat(), end.isoformat(), refresh=refresh)
        for name, series_id in {**MONTHLY_SERIES, **DAILY_SERIES}.items()
    }
    market = market_prices if market_prices is not None else download_market_history(warmup, end)
    positioning_rows = cftc_rows if cftc_rows is not None else fetch_gold_cot_history(
        refresh=refresh,
        start=warmup,
        end=end,
    )
    if "GLD" not in market or market["GLD"].dropna().empty:
        raise RuntimeError("No hay histórico de GLD para ejecutar el backtest")

    samples: list[dict[str, Any]] = []
    dates = _decision_dates(market["GLD"].dropna().index, start, end)
    for decision_at in dates:
        position = market.index.get_indexer([decision_at])[0]
        if position < 200:
            continue
        available = market.loc[:decision_at]
        gld = _market_metrics(available["GLD"])
        uup = _market_metrics(available["UUP"]) if "UUP" in available else {}
        macro = _macro_snapshot(series, decision_at.date())
        if "^VIX" in available and not available["^VIX"].dropna().empty:
            macro["VIX"] = float(available["^VIX"].dropna().iloc[-1])
        if macro.get("PointInTime_LastRelease") and macro["PointInTime_LastRelease"] > decision_at.date().isoformat():
            raise AssertionError("Se detectó información posterior al corte")
        positioning = summarize_gold_positioning(
            positioning_rows,
            as_of=decision_at.date(),
            gold_momentum_1m=gld.get("momentum_1m"),
        )
        macro.update(positioning_data_fields(positioning))
        if positioning.get("release_at"):
            release_day = str(positioning["release_at"])[:10]
            if release_day > decision_at.date().isoformat():
                raise AssertionError("Se detectó un informe CFTC aún no publicado")
        # El backtest evalúa el candidato CFTC aunque la puerta de producción
        # siga cerrada. La ablación decide después si puede puntuar en vivo.
        outlook = build_gold_outlook(
            macro, gld, uup, include_positioning_in_score=True
        )
        future_prices = market.loc[market.index > decision_at, "GLD"].dropna()
        entry = float(gld["price"] or 0)
        for horizon, key in ((21, "short_term"), (63, "medium_term")):
            if entry <= 0 or len(future_prices) < horizon:
                continue
            outcome = float(future_prices.iloc[horizon - 1])
            return_pct = (outcome / entry - 1) * 100
            momentum = float(gld.get("momentum_1m") or 0)
            real_change = float(macro.get("Real_Yield_10Y_1M_Change_Pp") or 0)
            dollar_momentum = float(uup.get("momentum_1m") or 0)
            horizon_key = "short" if horizon == 21 else "medium"
            ablation_probabilities = {
                group["id"]: probability
                for group in outlook["groups"]
                if float(group.get(f"{horizon_key}_weight") or 0) > 0
                and group.get(f"{horizon_key}_signal") is not None
                and (probability := _probability_without_group(outlook["groups"], horizon_key, group["id"])) is not None
            }
            samples.append({
                "decision_at": decision_at.date().isoformat(),
                "evaluated_at": future_prices.index[horizon - 1].date().isoformat(),
                "horizon_days": horizon,
                "entry_price": round(entry, 4),
                "outcome_price": round(outcome, 4),
                "return_pct": round(return_pct, 4),
                "direction_up": int(return_pct > 0),
                "model_probability": float(outlook[key]["probability_up"]),
                "momentum_probability": round(max(15, min(85, 50 + momentum * 5)), 2),
                "macro_probability": round(max(15, min(85, 50 - dollar_momentum * 5 - real_change * 35)), 2),
                "coverage_pct": float(outlook[key]["coverage_pct"]),
                "latest_release_at": macro.get("PointInTime_LastRelease"),
                "latest_cftc_release_at": positioning.get("release_at"),
                "ablation_probabilities": ablation_probabilities,
            })

    horizons: dict[str, Any] = {}
    for horizon in (21, 63):
        rows = [row for row in samples if row["horizon_days"] == horizon]
        folds = []
        for train, test in walk_forward_splits(len(rows), min_train=24, test_size=6):
            test_rows = [rows[index] for index in test]
            folds.append({
                "train_size": len(train),
                "test_from": test_rows[0]["decision_at"],
                "test_to": test_rows[-1]["decision_at"],
                **_evaluation(test_rows, "model_probability"),
            })
        model_metrics = _evaluation(rows, "model_probability")
        horizons[str(horizon)] = {
            "model": model_metrics,
            "baseline_momentum": _evaluation(rows, "momentum_probability"),
            "baseline_dollar_real_yield": _evaluation(rows, "macro_probability"),
            "walk_forward_folds": folds,
            "ablation": _ablation_report(rows),
        }

    passes_baselines = True
    for horizon in (21, 63):
        result = horizons[str(horizon)]
        model = result["model"]
        baselines = [result["baseline_momentum"], result["baseline_dollar_real_yield"]]
        brier_pass = all(
            model["brier_score"] is not None
            and baseline["brier_score"] is not None
            and model["brier_score"] < baseline["brier_score"]
            for baseline in baselines
        )
        accuracy_pass = all(
            model["balanced_accuracy"] is not None
            and baseline["balanced_accuracy"] is not None
            and model["balanced_accuracy"] >= baseline["balanced_accuracy"]
            for baseline in baselines
        )
        result["passes_baselines"] = brier_pass and accuracy_pass
        passes_baselines = passes_baselines and result["passes_baselines"]

    positioning_checks = []
    for horizon in (21, 63):
        item = (horizons[str(horizon)].get("ablation") or {}).get("positioning") or {}
        positioning_checks.append(
            int(item.get("sample_size") or 0) >= 30
            and item.get("interpretation") == "APORTA"
            and float(item.get("delta_brier_vs_full") or 0) >= 0.002
            and float(item.get("delta_balanced_accuracy_vs_full") or 0) >= -0.02
        )
    positioning_promoted = bool(positioning_checks) and all(positioning_checks)

    report = {
        "status": "READY" if all(horizons[str(h)]["model"]["sample_size"] >= 30 for h in (21, 63)) else "INSUFFICIENT_DATA",
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "decision_policy": "Primera sesión de mercado desde el día 15 de cada mes",
        "point_in_time": True,
        "vintage_policy": "Primera publicación FRED/ALFRED (output_type=4); revisiones posteriores excluidas",
        "promotion_status": "CANDIDATE" if passes_baselines else "KEEP_PRELIMINARY",
        "passes_baselines": passes_baselines,
        "feature_gates": {
            "positioning": "ENABLED" if positioning_promoted else "CONTEXT_ONLY",
            "rule": "Aporta en Brier en 21 y 63 sesiones, n>=30 y sin deterioro material de precisión equilibrada",
        },
        "horizons": horizons,
        "samples": samples,
        "limitations": [
            "El modelo v1 usa pesos heurísticos fijos; las ventanas walk-forward evalúan, no entrenan pesos.",
            "GLD y UUP son proxies negociables y no sustituyen al oro spot ni al índice DXY.",
            "Costes, deslizamiento, flujos ETF y compras oficiales aún no están incluidos.",
            "CFTC usa fecha de publicación point-in-time; su peso en producción depende de la puerta de ablación.",
        ],
    }
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(report_path)
    return report


def load_gold_backtest_report(path: Path = GOLD_BACKTEST_REPORT) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "NOT_RUN", "point_in_time": False, "horizons": {}}


if __name__ == "__main__":
    result = run_gold_backtest()
    print(json.dumps({key: result[key] for key in ("status", "model_version", "period", "horizons")}, indent=2))
