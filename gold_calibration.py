"""Calibración y pesos aprendidos walk-forward para la perspectiva del oro.

Todo ajuste usa solo resultados vencidos antes de cada decisión. Los pesos
heurísticos de ``gold_outlook`` no cambian aquí: los candidatos se evalúan
fuera de muestra y solo informan si han demostrado algo.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np


LEARNED_FEATURES = (
    "inflation", "real_rates", "dollar", "energy", "activity",
    "liquidity", "risk", "technical", "positioning", "etf_holdings",
)
# Hipótesis elegida tras observar 2023–2025: la relación oro–tipos reales pudo
# cambiar con la congelación de reservas rusas y el ciclo de subidas de 2022.
REGIME_BREAK = "2022-03-01"
REGIME_FEATURE = "real_rates_post_2022"
RIDGE_PENALTY = 4.0
MIN_TRAIN = 24
_SHRINK_GRID = tuple(step / 20 for step in range(21))


def _brier(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    pairs = list(zip(probabilities, outcomes))
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def fit_shrinkage(rows: list[dict[str, Any]], key: str = "model_probability") -> dict[str, Any]:
    """Ajusta p' = base + k·(p − 50) con k ∈ [0, 1] minimizando Brier."""
    if len(rows) < MIN_TRAIN:
        return {"status": "INSUFFICIENT_DATA", "sample_size": len(rows), "base_pct": None, "k": None}
    outcomes = [int(row["direction_up"]) for row in rows]
    base = sum(outcomes) / len(outcomes) * 100
    k = min(
        _SHRINK_GRID,
        key=lambda value: (
            _brier([apply_shrinkage(float(row[key]), base, value) / 100 for row in rows], outcomes),
            value,
        ),
    )
    return {"status": "FITTED", "sample_size": len(rows), "base_pct": round(base, 2), "k": k}


def apply_shrinkage(probability: float, base_pct: float, k: float) -> float:
    return round(max(1.0, min(99.0, base_pct + k * (probability - 50))), 2)


def feature_vector(row: dict[str, Any], *, regime: bool) -> list[float]:
    signals = row.get("group_signals") or {}
    values = [float(signals.get(name) or 0.0) for name in LEARNED_FEATURES]
    if regime:
        post = str(row.get("decision_at") or "") >= REGIME_BREAK
        values.append(float(signals.get("real_rates") or 0.0) if post else 0.0)
    return values


def feature_names(*, regime: bool) -> list[str]:
    return list(LEARNED_FEATURES) + ([REGIME_FEATURE] if regime else [])


def fit_ridge_logistic(
    rows: list[dict[str, Any]], *, regime: bool, penalty: float = RIDGE_PENALTY
) -> dict[str, Any]:
    """Regresión logística con penalización L2 (intercepto sin penalizar)."""
    if len(rows) < MIN_TRAIN:
        return {"status": "INSUFFICIENT_DATA", "sample_size": len(rows)}
    x = np.array([[1.0, *feature_vector(row, regime=regime)] for row in rows])
    y = np.array([float(row["direction_up"]) for row in rows])
    weights = np.zeros(x.shape[1])
    ridge = np.eye(x.shape[1]) * penalty
    ridge[0, 0] = 0.0
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-x @ weights))
        gradient = x.T @ (p - y) + ridge @ weights
        hessian = (x.T * (p * (1 - p))) @ x + ridge + np.eye(x.shape[1]) * 1e-9
        step = np.linalg.solve(hessian, gradient)
        weights -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    names = feature_names(regime=regime)
    return {
        "status": "FITTED",
        "sample_size": len(rows),
        "penalty": penalty,
        "intercept": round(float(weights[0]), 4),
        "coefficients": {name: round(float(value), 4) for name, value in zip(names, weights[1:])},
    }


def predict_logistic(model: dict[str, Any], row: dict[str, Any], *, regime: bool) -> float | None:
    if model.get("status") != "FITTED":
        return None
    names = feature_names(regime=regime)
    values = feature_vector(row, regime=regime)
    logit = float(model["intercept"]) + sum(float(model["coefficients"][name]) * value for name, value in zip(names, values))
    return round(max(1.0, min(99.0, 100.0 / (1.0 + math.exp(-logit)))), 2)


CANDIDATES = {
    "calibrated": "calibrated_probability",
    "learned": "learned_probability",
    "learned_regime": "learned_regime_probability",
}


def walk_forward_candidates(folds: Iterable[tuple[list[dict[str, Any]], list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Añade a cada corte de prueba las probabilidades de los tres candidatos."""
    evaluated: list[dict[str, Any]] = []
    for train, test in folds:
        shrink = fit_shrinkage(train)
        learned = fit_ridge_logistic(train, regime=False)
        learned_regime = fit_ridge_logistic(train, regime=True)
        for row in test:
            evaluated.append({
                **row,
                "calibrated_probability": (
                    apply_shrinkage(float(row["model_probability"]), shrink["base_pct"], shrink["k"])
                    if shrink["status"] == "FITTED" else None
                ),
                "calibration_k": shrink.get("k"),
                "learned_probability": predict_logistic(learned, row, regime=False),
                "learned_regime_probability": predict_logistic(learned_regime, row, regime=True),
            })
    return evaluated


def live_calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Parámetros ajustados con todos los cortes vencidos para aplicar en vivo."""
    return {
        "shrinkage": fit_shrinkage(rows),
        "learned": fit_ridge_logistic(rows, regime=False),
        "learned_regime": fit_ridge_logistic(rows, regime=True),
    }


def calibrate_live_horizon(horizon: dict[str, Any], calibration: dict[str, Any] | None, *, eligible: bool) -> dict[str, Any]:
    """Añade la probabilidad calibrada sin sustituir la heurística original."""
    shrink = (calibration or {}).get("shrinkage") or {}
    probability = horizon.get("probability_up")
    if shrink.get("status") != "FITTED" or probability is None:
        return {**horizon, "calibration": {"status": "UNAVAILABLE", "eligible": False}}
    calibrated = apply_shrinkage(float(probability), float(shrink["base_pct"]), float(shrink["k"]))
    k = float(shrink["k"])
    return {
        **horizon,
        "probability_calibrated": calibrated,
        "calibration": {
            "status": "FITTED",
            "eligible": eligible,
            "k": k,
            "base_pct": shrink["base_pct"],
            "sample_size": shrink["sample_size"],
            "note": (
                "La señal no mejora la frecuencia histórica: la probabilidad calibrada coincide con la base."
                if k == 0 else
                f"Se conserva el {k * 100:.0f}% de la desviación de la señal sobre la frecuencia histórica."
            ),
        },
    }
