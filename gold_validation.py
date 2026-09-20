"""Validación temporal de las perspectivas de oro persistidas por NEXUS.

No entrena ni valida con series FRED revisadas como si fueran point-in-time.
Las métricas solo se calculan sobre predicciones ya emitidas y resultados cuyo
horizonte ha vencido posteriormente.
"""

from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from config import GOLD_HISTORY_DB
from gold_history import initialize_gold_history


def brier_score(probabilities: Iterable[float], outcomes: Iterable[int]) -> float | None:
    pairs = list(zip(probabilities, outcomes))
    if not pairs:
        return None
    errors = [(max(0.0, min(1.0, float(prob))) - int(outcome)) ** 2 for prob, outcome in pairs]
    return round(sum(errors) / len(errors), 6)


def balanced_accuracy(probabilities: Iterable[float], outcomes: Iterable[int]) -> float | None:
    pairs = [(float(prob) >= 0.5, bool(outcome)) for prob, outcome in zip(probabilities, outcomes)]
    positives = [predicted == actual for predicted, actual in pairs if actual]
    negatives = [predicted == actual for predicted, actual in pairs if not actual]
    if not positives or not negatives:
        return None
    return round(((sum(positives) / len(positives)) + (sum(negatives) / len(negatives))) / 2, 6)


def calibration_bins(
    probabilities: Iterable[float],
    outcomes: Iterable[int],
    *,
    bin_width: float = 0.1,
) -> list[dict[str, Any]]:
    width = max(0.05, min(0.5, float(bin_width)))
    buckets: dict[int, list[tuple[float, int]]] = {}
    for probability, outcome in zip(probabilities, outcomes):
        probability = max(0.0, min(1.0, float(probability)))
        index = min(int(probability / width), int(1 / width) - 1)
        buckets.setdefault(index, []).append((probability, int(outcome)))
    return [
        {
            "from": round(index * width, 2),
            "to": round(min(1.0, (index + 1) * width), 2),
            "count": len(values),
            "mean_probability": round(sum(value[0] for value in values) / len(values), 4),
            "observed_frequency": round(sum(value[1] for value in values) / len(values), 4),
        }
        for index, values in sorted(buckets.items())
    ]


def walk_forward_splits(
    sample_count: int,
    *,
    min_train: int = 24,
    test_size: int = 6,
) -> list[tuple[range, range]]:
    """Ventanas expansivas; el conjunto de prueba siempre es posterior."""
    if min_train < 1 or test_size < 1:
        raise ValueError("min_train y test_size deben ser positivos")
    splits: list[tuple[range, range]] = []
    train_end = min_train
    while train_end < sample_count:
        test_end = min(sample_count, train_end + test_size)
        splits.append((range(0, train_end), range(train_end, test_end)))
        train_end = test_end
    return splits


def _iso_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def settle_predictions_from_prices(
    price_rows: Sequence[tuple[str, float]],
    *,
    db_path: Path = GOLD_HISTORY_DB,
) -> int:
    """Liquida horizontes vencidos usando solo sesiones posteriores a la captura."""
    clean_prices = sorted(
        (
            (_iso_date(raw_date), float(price))
            for raw_date, price in price_rows
            if price is not None and math.isfinite(float(price)) and float(price) > 0
        ),
        key=lambda item: item[0],
    )
    if not clean_prices:
        return 0
    initialize_gold_history(db_path)
    inserted = 0
    with closing(sqlite3.connect(Path(db_path), timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        predictions = connection.execute(
            """
            SELECT id, captured_at, entry_price, short_horizon_days, medium_horizon_days
            FROM gold_predictions WHERE entry_price IS NOT NULL ORDER BY captured_at
            """
        ).fetchall()
        for prediction in predictions:
            captured_date = _iso_date(prediction["captured_at"])
            future = [(day, price) for day, price in clean_prices if day > captured_date]
            entry = float(prediction["entry_price"])
            for horizon in {
                int(prediction["short_horizon_days"]),
                int(prediction["medium_horizon_days"]),
            }:
                # La primera fila es la primera sesión posterior; índice h-1 = h sesiones.
                if horizon < 1 or len(future) < horizon:
                    continue
                evaluated_at, outcome_price = future[horizon - 1]
                return_pct = (outcome_price / entry - 1) * 100
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO gold_prediction_outcomes
                    (prediction_id, horizon_days, evaluated_at, outcome_price, return_pct, direction_up)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(prediction["id"]), horizon, evaluated_at.isoformat(),
                        outcome_price, return_pct, int(return_pct > 0),
                    ),
                )
                inserted += int(cursor.rowcount > 0)
        connection.commit()
    return inserted


def validation_summary(
    *,
    horizon_days: int,
    db_path: Path = GOLD_HISTORY_DB,
) -> dict[str, Any]:
    if not Path(db_path).exists():
        return {"horizon_days": horizon_days, "sample_size": 0, "status": "INSUFFICIENT_DATA"}
    initialize_gold_history(db_path)
    probability_column = "short_probability" if horizon_days == 21 else "medium_probability"
    with closing(sqlite3.connect(Path(db_path), timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT p.{probability_column} AS probability, o.direction_up, o.return_pct,
                   p.captured_at, o.evaluated_at
            FROM gold_prediction_outcomes o
            JOIN gold_predictions p ON p.id = o.prediction_id
            WHERE o.horizon_days = ?
            ORDER BY p.captured_at
            """,
            (horizon_days,),
        ).fetchall()
    probabilities = [float(row["probability"]) / 100 for row in rows]
    outcomes = [int(row["direction_up"]) for row in rows]
    sample_size = len(rows)
    return {
        "horizon_days": horizon_days,
        "sample_size": sample_size,
        "status": "READY" if sample_size >= 30 else "INSUFFICIENT_DATA",
        "brier_score": brier_score(probabilities, outcomes),
        "balanced_accuracy": balanced_accuracy(probabilities, outcomes),
        "mean_return_pct": round(sum(float(row["return_pct"]) for row in rows) / sample_size, 4)
        if sample_size else None,
        "calibration": calibration_bins(probabilities, outcomes),
        "walk_forward_folds": len(walk_forward_splits(sample_size, min_train=24, test_size=6))
        if sample_size >= 24 else 0,
        "point_in_time_warning": (
            "Solo evalúa predicciones emitidas en vivo. No autoriza usar históricos FRED revisados "
            "como si fueran vintages de publicación."
        ),
    }
