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


def _ridge_matrix(size: int, penalty: float) -> np.ndarray:
    ridge = np.eye(size) * penalty
    ridge[0, 0] = 0.0
    return ridge


def _fit_logistic_matrix(x: np.ndarray, y: np.ndarray, penalty: float) -> np.ndarray:
    """IRLS con penalización L2; la primera columna es el intercepto sin penalizar."""
    weights = np.zeros(x.shape[1])
    ridge = _ridge_matrix(x.shape[1], penalty)
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-x @ weights))
        gradient = x.T @ (p - y) + ridge @ weights
        hessian = (x.T * (p * (1 - p))) @ x + ridge + np.eye(x.shape[1]) * 1e-9
        step = np.linalg.solve(hessian, gradient)
        weights -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return weights


def _fit_linear_matrix(x: np.ndarray, y: np.ndarray, penalty: float) -> np.ndarray:
    return np.linalg.solve(x.T @ x + _ridge_matrix(x.shape[1], penalty) + np.eye(x.shape[1]) * 1e-9, x.T @ y)


def fit_ridge_logistic(
    rows: list[dict[str, Any]], *, regime: bool, penalty: float = RIDGE_PENALTY
) -> dict[str, Any]:
    """Regresión logística con penalización L2 (intercepto sin penalizar)."""
    if len(rows) < MIN_TRAIN:
        return {"status": "INSUFFICIENT_DATA", "sample_size": len(rows)}
    x = np.array([[1.0, *feature_vector(row, regime=regime)] for row in rows])
    y = np.array([float(row["direction_up"]) for row in rows])
    weights = _fit_logistic_matrix(x, y, penalty)
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


# Señales en cambios calculadas en el backtest (``gold_backtest.compact_features``).
COMPACT_FEATURES = (
    "real_yield_change_3m", "breakeven_change_3m", "dollar_momentum_3m",
    "gold_momentum_12m", "vix_log",
)
PENALTY_GRID = (0.5, 2.0, 8.0, 32.0, 128.0)
# 2008 y 2020 producen señales de más de 5σ.
WINSOR_LIMIT = 3.0
# Con menos de cinco años un tramo casi siempre alcista (2005–2008) fija un
# intercepto extremo; 24 cortes solapados a 63 sesiones son ~8 independientes.
MIN_TRAIN_COMPACT = 60
# En unidades de volatilidad un paseo aleatorio tiene dispersión 1; los
# rendimientos solapados del entrenamiento la subestiman.
MIN_RETURN_SPREAD = 1.0
MIN_VALIDATION = 12


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _clamp_pct(probability: float) -> float:
    return round(max(1.0, min(99.0, probability * 100)), 2)


def drift_z(row: dict[str, Any]) -> float | None:
    """Deriva esperada en unidades de volatilidad del horizonte: μ·√h / σ."""
    drift, volatility = row.get("trend_drift"), row.get("trend_volatility")
    if drift is None or not volatility:
        return None
    return float(drift) * math.sqrt(int(row["horizon_days"])) / float(volatility)


def return_z(row: dict[str, Any]) -> float | None:
    """Rendimiento logarítmico realizado en unidades de volatilidad del horizonte."""
    volatility, log_return = row.get("trend_volatility"), row.get("log_return")
    if log_return is None or not volatility:
        return None
    return float(log_return) / (float(volatility) * math.sqrt(int(row["horizon_days"])))


def trend_probability(row: dict[str, Any]) -> float | None:
    z = drift_z(row)
    return _clamp_pct(_normal_cdf(z)) if z is not None else None


class _Standardizer:
    """Media y desviación del entrenamiento; los ausentes quedan en la media."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.stats: dict[str, tuple[float, float]] = {}
        for name in COMPACT_FEATURES:
            values = [float(v) for row in rows if (v := (row.get("compact_features") or {}).get(name)) is not None]
            if len(values) >= 2:
                spread = float(np.std(values))
                self.stats[name] = (float(np.mean(values)), spread if spread > 0 else 1.0)

    def vector(self, row: dict[str, Any]) -> list[float]:
        features = row.get("compact_features") or {}
        result = [1.0]
        for name in COMPACT_FEATURES:
            mean, spread = self.stats.get(name, (0.0, 1.0))
            value = features.get(name)
            if value is None or name not in self.stats:
                result.append(0.0)
            else:
                result.append(max(-WINSOR_LIMIT, min(WINSOR_LIMIT, (float(value) - mean) / spread)))
        return result


def _fit_compact(kind: str, rows: list[dict[str, Any]], penalty: float):
    """Devuelve una función fila → probabilidad (%) o ``None`` si no hay datos."""
    if kind == "compact_logistic":
        usable = [row for row in rows if row.get("compact_features")]
    else:
        usable = [row for row in rows if return_z(row) is not None
                  and (kind != "return_trend" or drift_z(row) is not None)]
    if len(usable) < MIN_TRAIN_COMPACT:
        return None
    scaler = _Standardizer(usable)
    x = np.array([scaler.vector(row) for row in usable])
    if kind == "compact_logistic":
        weights = _fit_logistic_matrix(x, np.array([float(row["direction_up"]) for row in usable]), penalty)

        def predict(row: dict[str, Any]) -> float | None:
            if not row.get("compact_features"):
                return None
            return _clamp_pct(1.0 / (1.0 + math.exp(-float(np.dot(weights, scaler.vector(row))))))
        return predict

    offsets = np.array([drift_z(row) if kind == "return_trend" else 0.0 for row in usable])
    target = np.array([return_z(row) for row in usable]) - offsets
    weights = _fit_linear_matrix(x, target, penalty)
    residual = target - x @ weights
    spread = max(float(np.std(residual)), MIN_RETURN_SPREAD)

    def predict(row: dict[str, Any]) -> float | None:
        offset = drift_z(row) if kind == "return_trend" else 0.0
        if offset is None:
            return None
        return _clamp_pct(_normal_cdf((offset + float(np.dot(weights, scaler.vector(row)))) / spread))
    return predict


def select_penalty(kind: str, rows: list[dict[str, Any]]) -> float:
    """Validación anidada: el último tercio del entrenamiento, purgado, elige λ."""
    ordered = sorted(rows, key=lambda row: row["decision_at"])
    size = max(MIN_VALIDATION, len(ordered) // 3)
    validation = ordered[-size:]
    inner = [row for row in ordered[:-size] if row["evaluated_at"] < validation[0]["decision_at"]]
    if len(inner) < MIN_TRAIN_COMPACT or len(validation) < MIN_VALIDATION:
        return RIDGE_PENALTY
    scores = []
    for penalty in PENALTY_GRID:
        predict = _fit_compact(kind, inner, penalty)
        pairs = [(p / 100, int(row["direction_up"])) for row in validation
                 if predict and (p := predict(row)) is not None]
        if len(pairs) >= MIN_VALIDATION:
            scores.append((_brier(*zip(*pairs)), penalty))
    return min(scores)[1] if scores else RIDGE_PENALTY


COMPACT_MODELS = ("compact_logistic", "return_compact", "return_trend")

CANDIDATES = {
    "calibrated": "calibrated_probability",
    "learned": "learned_probability",
    "learned_regime": "learned_regime_probability",
    "trend": "trend_probability",
    "compact_logistic": "compact_logistic_probability",
    "return_compact": "return_compact_probability",
    "return_trend": "return_trend_probability",
}


def walk_forward_candidates(folds: Iterable[tuple[list[dict[str, Any]], list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Añade a cada corte de prueba las probabilidades de todos los candidatos."""
    evaluated: list[dict[str, Any]] = []
    for train, test in folds:
        shrink = fit_shrinkage(train)
        learned = fit_ridge_logistic(train, regime=False)
        learned_regime = fit_ridge_logistic(train, regime=True)
        compact = {}
        for kind in COMPACT_MODELS:
            penalty = select_penalty(kind, train)
            compact[kind] = (penalty, _fit_compact(kind, train, penalty))
        for row in test:
            item = {
                **row,
                "calibrated_probability": (
                    apply_shrinkage(float(row["model_probability"]), shrink["base_pct"], shrink["k"])
                    if shrink["status"] == "FITTED" else None
                ),
                "calibration_k": shrink.get("k"),
                "learned_probability": predict_logistic(learned, row, regime=False),
                "learned_regime_probability": predict_logistic(learned_regime, row, regime=True),
                "trend_probability": trend_probability(row),
            }
            for kind, (penalty, predict) in compact.items():
                item[f"{kind}_probability"] = predict(row) if predict else None
                item[f"{kind}_penalty"] = penalty
            evaluated.append(item)
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
