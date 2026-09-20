"""Persistencia auditable para observaciones y perspectivas del oro.

La base diferencia el periodo económico de la fecha en que NEXUS observó el
dato. Las series FRED actuales se guardan como revisables y no se consideran
point-in-time hasta disponer de fecha de publicación o vintage verificable.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from config import GOLD_HISTORY_DB


_DB_LOCK = threading.RLock()

OBSERVATION_SPECS: dict[str, tuple[str, str | None]] = {
    "CPI_MoM_Pct": ("%", "CPI_AsOf"),
    "CPI_3M_Annualized_Pct": ("%", "CPI_AsOf"),
    "CPI_YoY_Pct": ("%", "CPI_AsOf"),
    "Core_CPI_MoM_Pct": ("%", "Core_CPI_AsOf"),
    "Core_CPI_3M_Annualized_Pct": ("%", "Core_CPI_AsOf"),
    "Core_CPI_YoY_Pct": ("%", "Core_CPI_AsOf"),
    "PCE_MoM_Pct": ("%", "PCE_AsOf"),
    "PCE_3M_Annualized_Pct": ("%", "PCE_AsOf"),
    "PCE_YoY_Pct": ("%", "PCE_AsOf"),
    "Core_PCE_MoM_Pct": ("%", "Core_PCE_AsOf"),
    "Core_PCE_3M_Annualized_Pct": ("%", "Core_PCE_AsOf"),
    "Core_PCE_YoY_Pct": ("%", "Core_PCE_AsOf"),
    "Energy_CPI_MoM_Pct": ("%", "Energy_CPI_AsOf"),
    "Energy_CPI_YoY_Pct": ("%", "Energy_CPI_AsOf"),
    "Real_Yield_10Y_Pct": ("%", "Real_Yield_10Y_AsOf"),
    "Real_Yield_10Y_1M_Change_Pp": ("pp", "Real_Yield_10Y_AsOf"),
    "Breakeven_10Y_Pct": ("%", "Breakeven_10Y_AsOf"),
    "Breakeven_10Y_1M_Change_Pp": ("pp", "Breakeven_10Y_AsOf"),
    "WTI_Price": ("USD", "WTI_AsOf"),
    "WTI_1M_Change_Pct": ("%", "WTI_AsOf"),
    "Unemployment_Rate_Pct": ("%", "Unemployment_AsOf"),
    "Unemployment_1M_Change_Pp": ("pp", "Unemployment_AsOf"),
    "Payrolls_Level_Thousands": ("thousands", "Payrolls_AsOf"),
    "Payrolls_1M_Change_Thousands": ("thousands", "Payrolls_AsOf"),
    "Industrial_Production_MoM_Pct": ("%", "Industrial_Production_AsOf"),
    "M2_Change_Pct": ("%", "M2_AsOf"),
    "China_M2_YoY_Pct": ("%", "China_M2_AsOf"),
    "CFTC_MM_Net_Contracts": ("contracts", "CFTC_AsOf"),
    "CFTC_MM_Net_Pct_OI": ("% OI", "CFTC_AsOf"),
    "CFTC_MM_Weekly_Change_Contracts": ("contracts", "CFTC_AsOf"),
    "CFTC_MM_4W_Change_Contracts": ("contracts", "CFTC_AsOf"),
    "CFTC_MM_Percentile_3Y": ("percentile", "CFTC_AsOf"),
    "CFTC_MM_ZScore_3Y": ("z-score", "CFTC_AsOf"),
    "VIX": ("index", None),
}


def _utc_iso(value: str | datetime | None = None) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _period_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def initialize_gold_history(db_path: Path = GOLD_HISTORY_DB) -> None:
    with _DB_LOCK, closing(_connect(Path(db_path))) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS gold_observations (
                id INTEGER PRIMARY KEY,
                metric TEXT NOT NULL,
                period TEXT NOT NULL,
                release_at TEXT,
                observed_at TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                source TEXT NOT NULL,
                quality TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0,
                point_in_time INTEGER NOT NULL DEFAULT 0,
                UNIQUE(metric, period, revision)
            );
            CREATE INDEX IF NOT EXISTS idx_gold_observations_metric_period
                ON gold_observations(metric, period, revision DESC);

            CREATE TABLE IF NOT EXISTS gold_predictions (
                id INTEGER PRIMARY KEY,
                captured_at TEXT NOT NULL,
                model_version TEXT NOT NULL,
                model_status TEXT NOT NULL,
                instrument TEXT NOT NULL DEFAULT 'GLD',
                entry_price REAL,
                short_horizon_days INTEGER NOT NULL,
                short_probability REAL NOT NULL,
                short_score REAL NOT NULL,
                short_label TEXT NOT NULL,
                short_confidence TEXT NOT NULL,
                short_coverage REAL NOT NULL,
                medium_horizon_days INTEGER NOT NULL,
                medium_probability REAL NOT NULL,
                medium_score REAL NOT NULL,
                medium_label TEXT NOT NULL,
                medium_confidence TEXT NOT NULL,
                medium_coverage REAL NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE(captured_at, model_version)
            );
            CREATE TABLE IF NOT EXISTS gold_prediction_factors (
                prediction_id INTEGER NOT NULL REFERENCES gold_predictions(id) ON DELETE CASCADE,
                factor_id TEXT NOT NULL,
                available INTEGER NOT NULL,
                coverage REAL NOT NULL,
                short_contribution REAL,
                medium_contribution REAL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY(prediction_id, factor_id)
            );

            CREATE TABLE IF NOT EXISTS gold_prediction_outcomes (
                prediction_id INTEGER NOT NULL REFERENCES gold_predictions(id) ON DELETE CASCADE,
                horizon_days INTEGER NOT NULL,
                evaluated_at TEXT NOT NULL,
                outcome_price REAL NOT NULL,
                return_pct REAL NOT NULL,
                direction_up INTEGER NOT NULL,
                PRIMARY KEY(prediction_id, horizon_days)
            );
            """
        )


def _insert_observation(
    connection: sqlite3.Connection,
    *,
    metric: str,
    period: str,
    observed_at: str,
    value: float,
    unit: str,
    source: str,
    quality: str,
    release_at: str | None,
    point_in_time: bool,
) -> bool:
    latest = connection.execute(
        """
        SELECT value, revision FROM gold_observations
        WHERE metric = ? AND period = ? ORDER BY revision DESC LIMIT 1
        """,
        (metric, period),
    ).fetchone()
    if latest is not None and math.isclose(float(latest["value"]), value, rel_tol=0, abs_tol=1e-9):
        return False
    revision = int(latest["revision"]) + 1 if latest is not None else 0
    connection.execute(
        """
        INSERT INTO gold_observations
        (metric, period, release_at, observed_at, value, unit, source, quality, revision, point_in_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric, period, release_at, observed_at, value, unit, source,
            quality, revision, int(point_in_time),
        ),
    )
    return True


def record_gold_snapshot(
    data: dict[str, Any],
    outlook: dict[str, Any],
    *,
    captured_at: str | datetime | None = None,
    db_path: Path = GOLD_HISTORY_DB,
) -> dict[str, int]:
    """Guarda observaciones y predicción; rechaza periodos posteriores al corte."""
    observed_at = _utc_iso(captured_at)
    cutoff = datetime.fromisoformat(observed_at).date()
    quality_map = data.get("DataQuality") if isinstance(data.get("DataQuality"), dict) else {}
    inserted = 0
    unchanged = 0
    rejected_future = 0

    initialize_gold_history(db_path)
    with _DB_LOCK, closing(_connect(Path(db_path))) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for metric, (unit, as_of_key) in OBSERVATION_SPECS.items():
            value = _number(data.get(metric))
            if value is None:
                continue
            quality = quality_map.get(metric) if isinstance(quality_map.get(metric), dict) else {}
            raw_period = data.get(as_of_key) if as_of_key else observed_at[:10]
            period_date = _period_date(raw_period)
            if period_date is None:
                continue
            if period_date > cutoff:
                rejected_future += 1
                continue
            source = str(quality.get("source") or "unknown")
            status = str(quality.get("status") or "UNKNOWN")
            # Mercado observado en vivo puede fecharse en la captura. Para FRED
            # no se inventa release_at: sus revisiones actuales no son vintage.
            market_live = as_of_key is None and source.lower().startswith("yfinance")
            cftc_public = metric.startswith("CFTC_") and bool(data.get("CFTC_ReleaseAt"))
            release_at = str(data.get("CFTC_ReleaseAt")) if cftc_public else (observed_at if market_live else None)
            did_insert = _insert_observation(
                connection,
                metric=metric,
                period=period_date.isoformat(),
                observed_at=observed_at,
                value=value,
                unit=unit,
                source=source,
                quality=status,
                release_at=release_at,
                point_in_time=market_live or cftc_public,
            )
            inserted += int(did_insert)
            unchanged += int(not did_insert)

        short = outlook.get("short_term") or {}
        medium = outlook.get("medium_term") or {}
        model_version = str(outlook.get("version") or "unknown")
        existing_prediction = connection.execute(
            """
            SELECT id FROM gold_predictions
            WHERE model_version = ? AND substr(captured_at, 1, 10) = ?
            LIMIT 1
            """,
            (model_version, observed_at[:10]),
        ).fetchone()
        prediction_id = int(existing_prediction["id"]) if existing_prediction is not None else None
        prediction_inserted = 0
        if prediction_id is None:
            cursor = connection.execute(
                """
                INSERT INTO gold_predictions
                (captured_at, model_version, model_status, instrument, entry_price,
                 short_horizon_days, short_probability, short_score, short_label,
                 short_confidence, short_coverage, medium_horizon_days,
                 medium_probability, medium_score, medium_label, medium_confidence,
                 medium_coverage, payload_json)
                VALUES (?, ?, ?, 'GLD', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observed_at,
                    model_version,
                    str(outlook.get("status") or "UNKNOWN"),
                    _number((data.get("Assets") or {}).get("GLD", {}).get("price")),
                    int(short.get("horizon_days") or 21),
                    float(short.get("probability_up") or 50),
                    float(short.get("score") or 0),
                    str(short.get("label") or "NEUTRAL"),
                    str(short.get("confidence") or "BAJA"),
                    float(short.get("coverage_pct") or 0),
                    int(medium.get("horizon_days") or 63),
                    float(medium.get("probability_up") or 50),
                    float(medium.get("score") or 0),
                    str(medium.get("label") or "NEUTRAL"),
                    str(medium.get("confidence") or "BAJA"),
                    float(medium.get("coverage_pct") or 0),
                    json.dumps(outlook, ensure_ascii=False, sort_keys=True),
                ),
            )
            prediction_id = int(cursor.lastrowid)
            prediction_inserted = 1
        if prediction_inserted and prediction_id is not None:
            for group in outlook.get("groups") or []:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO gold_prediction_factors
                    (prediction_id, factor_id, available, coverage,
                     short_contribution, medium_contribution, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prediction_id,
                        str(group.get("id") or "unknown"),
                        int(bool(group.get("available"))),
                        float(group.get("coverage_pct") or 0),
                        _number(group.get("short_contribution")),
                        _number(group.get("medium_contribution")),
                        json.dumps(group, ensure_ascii=False, sort_keys=True),
                    ),
                )
        connection.commit()

    return {
        "observations_inserted": inserted,
        "observations_unchanged": unchanged,
        "future_observations_rejected": rejected_future,
        "prediction_inserted": prediction_inserted,
    }


def gold_history_summary(db_path: Path = GOLD_HISTORY_DB) -> dict[str, Any]:
    if not Path(db_path).exists():
        return {"observations": 0, "predictions": 0, "settled_outcomes": 0}
    initialize_gold_history(db_path)
    with _DB_LOCK, closing(_connect(Path(db_path))) as connection:
        observations = int(connection.execute("SELECT COUNT(*) FROM gold_observations").fetchone()[0])
        predictions = int(connection.execute("SELECT COUNT(*) FROM gold_predictions").fetchone()[0])
        outcomes = int(connection.execute("SELECT COUNT(*) FROM gold_prediction_outcomes").fetchone()[0])
        point_in_time = int(
            connection.execute("SELECT COUNT(*) FROM gold_observations WHERE point_in_time = 1").fetchone()[0]
        )
        latest = connection.execute("SELECT MAX(captured_at) FROM gold_predictions").fetchone()[0]
        recent_rows = connection.execute(
            """
            SELECT p.captured_at, p.short_probability, p.medium_probability,
                   p.short_label, p.medium_label,
                   short.return_pct AS short_return_pct,
                   medium.return_pct AS medium_return_pct
            FROM gold_predictions p
            LEFT JOIN gold_prediction_outcomes short
              ON short.prediction_id = p.id AND short.horizon_days = p.short_horizon_days
            LEFT JOIN gold_prediction_outcomes medium
              ON medium.prediction_id = p.id AND medium.horizon_days = p.medium_horizon_days
            ORDER BY p.captured_at DESC
            LIMIT 24
            """
        ).fetchall()
    return {
        "observations": observations,
        "point_in_time_observations": point_in_time,
        "predictions": predictions,
        "settled_outcomes": outcomes,
        "latest_prediction_at": latest,
        "recent_predictions": [
            {
                "captured_at": row["captured_at"],
                "short_probability": round(float(row["short_probability"]), 2),
                "medium_probability": round(float(row["medium_probability"]), 2),
                "short_label": row["short_label"],
                "medium_label": row["medium_label"],
                "short_return_pct": row["short_return_pct"],
                "medium_return_pct": row["medium_return_pct"],
            }
            for row in reversed(recent_rows)
        ],
    }


def gold_change_summary(
    current_outlook: dict[str, Any],
    *,
    captured_at: str | datetime | None = None,
    db_path: Path = GOLD_HISTORY_DB,
) -> dict[str, Any] | None:
    """Compara la lectura actual con la última captura de un día anterior."""
    if not Path(db_path).exists():
        return None
    current_at = _utc_iso(captured_at)
    initialize_gold_history(db_path)
    with _DB_LOCK, closing(_connect(Path(db_path))) as connection:
        row = connection.execute(
            """
            SELECT captured_at, payload_json
            FROM gold_predictions
            WHERE date(captured_at) < date(?)
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (current_at,),
        ).fetchone()
    if row is None:
        return None
    try:
        previous = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        return None

    def horizon_change(key: str) -> dict[str, Any]:
        current = current_outlook.get(key) or {}
        prior = previous.get(key) or {}
        current_probability = _number(current.get("probability_up"))
        prior_probability = _number(prior.get("probability_up"))
        return {
            "current_probability": current_probability,
            "previous_probability": prior_probability,
            "delta_probability": round(current_probability - prior_probability, 2)
            if current_probability is not None and prior_probability is not None else None,
            "current_label": current.get("label"),
            "previous_label": prior.get("label"),
            "label_changed": current.get("label") != prior.get("label"),
        }

    previous_groups = {
        str(group.get("id")): group for group in previous.get("groups") or [] if group.get("id")
    }
    drivers = []
    for group in current_outlook.get("groups") or []:
        key = str(group.get("id") or "")
        prior = previous_groups.get(key, {})
        short_current = _number(group.get("short_contribution"))
        short_previous = _number(prior.get("short_contribution"))
        medium_current = _number(group.get("medium_contribution"))
        medium_previous = _number(prior.get("medium_contribution"))
        short_delta = (
            round(short_current - short_previous, 2)
            if short_current is not None and short_previous is not None else None
        )
        medium_delta = (
            round(medium_current - medium_previous, 2)
            if medium_current is not None and medium_previous is not None else None
        )
        if short_delta is None and medium_delta is None:
            continue
        drivers.append({
            "id": key,
            "label": group.get("label") or key,
            "short_delta": short_delta,
            "medium_delta": medium_delta,
        })
    drivers.sort(
        key=lambda item: max(abs(item.get("short_delta") or 0), abs(item.get("medium_delta") or 0)),
        reverse=True,
    )
    short = horizon_change("short_term")
    medium = horizon_change("medium_term")
    moved = max(abs(short.get("delta_probability") or 0), abs(medium.get("delta_probability") or 0))
    changed_label = bool(short["label_changed"] or medium["label_changed"])
    if changed_label:
        headline = "Ha cambiado la dirección de al menos un horizonte"
    elif moved >= 3:
        headline = "La lectura se ha movido de forma relevante"
    else:
        headline = "La perspectiva se mantiene estable"
    return {
        "previous_captured_at": row["captured_at"],
        "headline": headline,
        "short": short,
        "medium": medium,
        "drivers": drivers[:3],
    }
