"""Referencias y diagnóstico temporal para resultados de oro solapados."""

from __future__ import annotations

import math
import random
from typing import Any


BASELINES = {
    "constant": "constant_probability",
    "historical_frequency": "historical_probability",
    "momentum": "momentum_probability",
    "dollar_real_yield": "macro_probability",
}


def assign_historical_baseline(rows: list[dict[str, Any]], minimum: int = 24) -> None:
    """La frecuencia solo conoce resultados vencidos antes de cada decisión."""
    for index, row in enumerate(rows):
        matured = [prior for prior in rows[:index] if prior["evaluated_at"] < row["decision_at"]]
        row["constant_probability"] = 50.0
        row["historical_train_size"] = len(matured)
        row["historical_train_latest_outcome"] = max((item["evaluated_at"] for item in matured), default=None)
        row["historical_probability"] = (
            sum(item["direction_up"] for item in matured) / len(matured) * 100
            if len(matured) >= minimum else None
        )


def purged_folds(rows: list[dict[str, Any]], minimum: int = 24, test_size: int = 6):
    """Cada entrenamiento termina antes de comenzar los resultados de prueba."""
    for start in range(minimum, len(rows), test_size):
        test = rows[start:start + test_size]
        train = [row for row in rows[:start] if row["evaluated_at"] < test[0]["decision_at"]]
        if len(train) >= minimum:
            probability = sum(row["direction_up"] for row in train) / len(train) * 100
            yield train, [{**row, "historical_probability": probability} for row in test]


def overlap_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    non_overlapping = 0
    last_end = ""
    max_overlap = 1
    for index, row in enumerate(rows):
        if row["decision_at"] > last_end:
            non_overlapping += 1
            last_end = row["evaluated_at"]
        active = sum(prior["evaluated_at"] >= row["decision_at"] for prior in rows[:index])
        max_overlap = max(max_overlap, active + 1)
    return {"sample_size": len(rows), "non_overlapping_count": non_overlapping,
            "max_concurrent_windows": max_overlap,
            "has_overlap": max_overlap > 1,
            "note": "El subconjunto sin solapamiento no estima el número efectivo de muestras independientes."}


def paired_brier_interval(
    rows: list[dict[str, Any]],
    baseline_key: str,
    *,
    draws: int = 1000,
    model_key: str = "model_probability",
) -> dict[str, Any]:
    """Bootstrap de bloques consecutivos para la diferencia NEXUS − referencia.

    Longitud mínima de seis cortes, ampliada si hay más ventanas concurrentes.
    El intervalo es aproximado; no demuestra independencia ni causalidad.
    """
    n = len(rows)
    block = max(6, overlap_diagnostics(rows)["max_concurrent_windows"])
    if n < max(30, block * 4):
        return {"status": "INSUFFICIENT_DATA", "sample_size": n, "block_length": block,
                "lower": None, "upper": None, "delta_brier": None}
    losses = [((row[model_key] / 100 - row["direction_up"]) ** 2
               - (row[baseline_key] / 100 - row["direction_up"]) ** 2) for row in rows]
    rng = random.Random(20260930)
    means = []
    for _ in range(draws):
        resampled = []
        while len(resampled) < n:
            start = rng.randrange(n - block + 1)
            resampled.extend(losses[start:start + block])
        means.append(sum(resampled[:n]) / n)
    means.sort()
    return {"status": "APPROXIMATE", "sample_size": n, "block_length": block,
            "confidence_level": 0.95, "resamples": draws,
            "delta_brier": round(sum(losses) / n, 6),
            "lower": round(means[math.floor(draws * 0.025)], 6),
            "upper": round(means[min(draws - 1, math.ceil(draws * 0.975))], 6)}
