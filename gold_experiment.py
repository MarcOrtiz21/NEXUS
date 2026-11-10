"""Experimento prospectivo manual. Nunca modifica la producción ni su confianza."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone, time
from pathlib import Path
from statistics import mean, stdev
from zoneinfo import ZoneInfo

from config import HISTORY_DIR, CACHE_DIR
from gold_backtest_stats import overlap_diagnostics, paired_brier_interval
from gold_validation import brier_score, balanced_accuracy, calibration_bins

EXPERIMENT_ID = "gold-trend-frequency-v1"
DB_PATH = HISTORY_DIR / "gold_experiments.sqlite3"
PRICE_PATH = CACHE_DIR / "gold_experiment_prices.json"
RULES = {"blend_trend": 0.5, "blend_frequency": 0.5, "drift_sessions": 756,
         "volatility_sessions": 63, "minimum_returns": 756, "cut_day": 15,
         "close_buffer_minutes": 15, "horizons": [21, 63],
         "minimum_outcomes": 30, "minimum_separated_cuts": 30,
         "frequency_policy": "FROZEN_AT_REGISTRATION", "activation": "NEVER_AUTOMATIC"}
NY = ZoneInfo("America/New_York")


def _instant(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("La fecha de corte debe tener zona horaria")
    return result.astimezone(timezone.utc)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _implementation():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS experiment_registry (
          id TEXT PRIMARY KEY, registered_at TEXT NOT NULL, manifest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS experiment_predictions (
          id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, captured_at TEXT NOT NULL,
          session TEXT NOT NULL, month TEXT NOT NULL, horizon INTEGER NOT NULL,
          entry REAL NOT NULL, probability REAL NOT NULL, trend REAL NOT NULL,
          frequency REAL NOT NULL, production REAL NOT NULL, inputs_hash TEXT NOT NULL,
          inputs_json TEXT NOT NULL,
          UNIQUE(experiment_id,month,horizon));
        CREATE TABLE IF NOT EXISTS experiment_outcomes (
          prediction_id INTEGER PRIMARY KEY, evaluated_at TEXT NOT NULL,
          price REAL NOT NULL, direction_up INTEGER NOT NULL);
        CREATE TRIGGER IF NOT EXISTS immutable_experiment_registry BEFORE UPDATE ON experiment_registry
          BEGIN SELECT RAISE(ABORT, 'Registro experimental inmutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_experiment_predictions BEFORE UPDATE ON experiment_predictions
          BEGIN SELECT RAISE(ABORT, 'Predicciones experimentales inmutables'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_experiment_outcomes BEFORE UPDATE ON experiment_outcomes
          BEGIN SELECT RAISE(ABORT, 'Resultados experimentales inmutables'); END;
    """)
    return c


def register_experiment(report, *, registered_at=None, db_path=DB_PATH):
    """Registro explícito único; el histórico previo solo fija la frecuencia base."""
    cutoff = _instant(registered_at)
    with closing(_connect(db_path)) as c:
        existing = c.execute("SELECT manifest FROM experiment_registry WHERE id=?", (EXPERIMENT_ID,)).fetchone()
        if existing:
            return json.loads(existing[0])
        if not report.get("compatible_with_live") or not report.get("model_fingerprint"):
            raise ValueError("Recalcula primero un informe compatible con producción")
        base = {}
        for horizon in RULES["horizons"]:
            known = [s for s in report.get("samples", []) if s["horizon_days"] == horizon
                     and s["evaluated_at"] < cutoff.astimezone(NY).date().isoformat()
                     and s["decision_at"] < s["evaluated_at"]]
            if len(known) < 24:
                raise ValueError("Faltan resultados históricos vencidos para fijar la frecuencia")
            base[str(horizon)] = {"probability": 100 * mean(s["direction_up"] for s in known),
                                  "sample_size": len(known),
                                  "last_outcome": max(s["evaluated_at"] for s in known)}
        manifest = {"id": EXPERIMENT_ID, "registered_at": cutoff.isoformat(), "rules": RULES,
                    "rules_hash": _hash(RULES), "implementation_hash": _implementation(),
                    "production_fingerprint": report["model_fingerprint"], "base": base,
                    "research_report_hash": _hash(report),
                    "historical_assumptions": report.get("temporal_quality"),
                    "methodology": "Promedio 50/50 de tendencia y frecuencia congelada. Solo cortes nuevos; no es una probabilidad validada ni una orden."}
        c.execute("INSERT INTO experiment_registry VALUES (?,?,?)", (EXPERIMENT_ID, cutoff.isoformat(), json.dumps(manifest)))
        c.commit()
        return manifest


def clean_prices(points, cutoff):
    """Cierres diarios, sin duplicados, futuros ni filas no finitas."""
    current = _instant(cutoff).astimezone(NY)
    values = {}
    for row in points:
        try:
            day = datetime.fromisoformat(str(row["date"])[:10]).date()
            price = float(row.get("close", row.get("value")))
        except (KeyError, ValueError, TypeError):
            continue
        if day.weekday() >= 5 or not math.isfinite(price) or price <= 0 or day > current.date():
            continue
        # También en cierres tempranos se espera hasta 16:15 ET, conservador.
        if day == current.date() and current.time() < time(16, 15):
            continue
        if day.isoformat() in values and values[day.isoformat()] != price:
            raise ValueError("Cierres contradictorios para la misma sesión")
        values[day.isoformat()] = price
    return sorted(values.items())


def predict_blend(prices, base, horizon):
    returns = [math.log(b[1] / a[1]) for a, b in zip(prices, prices[1:])]
    if len(returns) < RULES["minimum_returns"]:
        return None
    volatility = stdev(returns[-RULES["volatility_sessions"]:])
    if volatility <= 0:
        return None
    z = mean(returns[-RULES["drift_sessions"]:]) * math.sqrt(horizon) / volatility
    trend = max(1, min(99, 50 * (1 + math.erf(z / math.sqrt(2)))))
    return {"probability": round(0.5 * trend + 0.5 * base, 4),
            "trend": round(trend, 4), "frequency": round(base, 4)}


def load_prices(*, refresh=False, path=PRICE_PATH):
    """Solo una acción manual refresh descarga GLD; leer la vista no descarga."""
    cached = {}
    try:
        cached = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        pass
    if not refresh:
        return cached
    from data_ingestion import _yf_download
    frame = _yf_download(["GLD"], period="5y", timeout=20)
    if frame is None or frame.empty:
        return {**cached, "status": "STALE" if cached else "MISSING"}
    close = frame["Close"]
    if getattr(close, "ndim", 1) == 2:
        close = close["GLD"]
    points = [{"date": str(day.date()), "close": float(value)} for day, value in close.dropna().items()]
    payload = {"fetched_at": _instant().isoformat(), "status": "OK", "source": "Yahoo/GLD daily unadjusted", "points": points}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, allow_nan=False))
    temporary.replace(path)
    return payload


def experiment_summary(*, db_path=DB_PATH, cutoff=None):
    if not Path(db_path).exists():
        return {"status": "NOT_REGISTERED", "score_enabled": False, "horizons": []}
    now = _instant(cutoff)
    with closing(sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)) as c:
        c.row_factory = sqlite3.Row
        registry = c.execute("SELECT manifest FROM experiment_registry WHERE id=?", (EXPERIMENT_ID,)).fetchone()
        if not registry:
            return {"status": "NOT_REGISTERED", "score_enabled": False, "horizons": []}
        manifest = json.loads(registry[0])
        result = {"status": "SHADOW", "score_enabled": False, "registered_at": manifest["registered_at"],
                  "id": EXPERIMENT_ID, "methodology": manifest["methodology"], "horizons": [],
                  "capture_note": "Registro solo con actualización manual, desde el día 15 y después de 16:15 Nueva York; datos activos actualizados."}
        if manifest["implementation_hash"] != _implementation() or manifest["rules_hash"] != _hash(RULES):
            result["status"] = "RULES_CHANGED"
        for h in RULES["horizons"]:
            rows = [dict(row) for row in c.execute("""SELECT p.*,o.evaluated_at,o.direction_up FROM experiment_predictions p
                JOIN experiment_outcomes o ON o.prediction_id=p.id WHERE p.experiment_id=? AND p.horizon=?
                AND o.evaluated_at < ? AND datetime(p.captured_at)<=datetime(?)
                ORDER BY p.captured_at""", (EXPERIMENT_ID,h,now.astimezone(NY).date().isoformat(),now.isoformat()))]
            rows = [{**r, "decision_at": r["session"], "model_probability": r["probability"],
                     "constant_probability": 50.0} for r in rows]
            n = len(rows)
            separated = overlap_diagnostics(rows)["non_overlapping_count"]
            publish = n >= 30 and separated >= 30
            references = {"constant": "constant_probability", "frequency": "frequency", "trend": "trend", "production": "production"}
            intervals = {name: paired_brier_interval(rows, key) for name,key in references.items()} if publish else {}
            brier = brier_score([r["probability"]/100 for r in rows], [r["direction_up"] for r in rows]) if publish else None
            accuracy = balanced_accuracy([r["probability"]/100 for r in rows], [r["direction_up"] for r in rows]) if publish else None
            passed = publish and accuracy is not None and all(i.get("upper") is not None and i["upper"] < 0 for i in intervals.values())
            if passed:
                passed = all((a := balanced_accuracy([r[key]/100 for r in rows],[r["direction_up"] for r in rows])) is not None and accuracy >= a for key in references.values())
            total = c.execute("SELECT count(*) FROM experiment_predictions WHERE experiment_id=? AND horizon=?", (EXPERIMENT_ID,h)).fetchone()[0]
            latest = c.execute("SELECT probability,trend,frequency,session FROM experiment_predictions WHERE experiment_id=? AND horizon=? ORDER BY captured_at DESC LIMIT 1", (EXPERIMENT_ID,h)).fetchone()
            result["horizons"].append({"horizon_days":h,"predictions":total,"settled":n,"separated_cuts":separated,
                "base_probability":round(manifest["base"][str(h)]["probability"],2),"latest":dict(latest) if latest else None,
                "metrics_publishable":publish,"brier_score":brier,"balanced_accuracy":accuracy,"comparisons":intervals,
                "status":"MANUAL_REVIEW_CANDIDATE" if passed else "PRELIMINARY" if publish else "INSUFFICIENT_DATA",
                "calibration":calibration_bins([r["probability"]/100 for r in rows],[r["direction_up"] for r in rows]) if publish else []})
        return result


def update_experiment(outlook, *, captured_at=None, persist=False, prices=None, db_path=DB_PATH):
    now = _instant(captured_at)
    view = experiment_summary(db_path=db_path, cutoff=now)
    if view["status"] in {"NOT_REGISTERED", "RULES_CHANGED"}:
        return view
    with closing(sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)) as c:
        manifest = json.loads(c.execute("SELECT manifest FROM experiment_registry WHERE id=?",(EXPERIMENT_ID,)).fetchone()[0])
    if outlook.get("model_fingerprint") != manifest["production_fingerprint"]:
        return {**view,"status":"PRODUCTION_CHANGED","capture_note":"Producción cambió: registrar una nueva versión del experimento, no sobrescribir esta."}
    cache = prices if prices is not None else load_prices(refresh=persist)
    try:
        fetched = _instant(cache["fetched_at"])
        # Corte experimental propio: no retrofechar la descarga usando la caché del snapshot principal.
        cutoff = _instant() if captured_at is None else now
        fresh = cache.get("status") == "OK" and 0 <= (cutoff-fetched).total_seconds() <= 3600
        points = clean_prices(cache.get("points",[]), cutoff)
    except (KeyError, ValueError, TypeError):
        fresh, points, cutoff = False, [], now
    local = cutoff.astimezone(NY)
    previews = []
    for h in RULES["horizons"]:
        value = predict_blend(points,manifest["base"][str(h)]["probability"],h)
        previews.append({"horizon_days":h,**(value or {})})
    view["preview"] = previews
    view["price_as_of"] = points[-1][0] if points else None
    view["price_status"] = "OK" if fresh else "STALE" if points else "MISSING"
    production_ok = all((outlook.get(key) or {}).get("fresh_coverage_pct",0) >= 90 for key in ("short_term","medium_term"))
    technical = next((g for g in outlook.get("groups",[]) if g.get("id") == "technical"), {})
    entry = next((d.get("value") for d in technical.get("details",[]) if d.get("label") == "Precio GLD"), None)
    aligned = entry is not None and points and abs(float(entry)-points[-1][1]) <= 0.01
    eligible = fresh and points and local.day >= 15 and local.time() >= time(16,15) and points[-1][0] == local.date().isoformat() and cutoff > _instant(manifest["registered_at"]) and production_ok and aligned and all("probability" in p for p in previews)
    view["capture_note"] = "Solo vista previa; la próxima captura exige actualización manual tras el cierre desde el día 15." if not eligible else "Corte mensual disponible; solo se guarda al actualizar manualmente."
    if not fresh or not points:
        view["capture_note"] = "Falta histórico diario GLD actualizado (5 años). La actualización manual prepara la caché."
    elif not production_ok:
        view["capture_note"] = "Datos activos insuficientemente actualizados: no se guarda un corte experimental."
    elif not aligned:
        view["capture_note"] = "Producción y experimento no comparten el mismo cierre GLD; actualiza los datos antes de registrar."
    if persist:
        with closing(_connect(db_path)) as c:
            if eligible:
                for p,key in zip(previews,("short_term","medium_term")):
                    probability = float(outlook[key]["probability_up"])
                    if not math.isfinite(probability) or not 0 <= probability <= 100:
                        raise ValueError("Referencia de producción inválida")
                    inputs = {"prices":points,"production_probability":probability,
                              "production_fingerprint":outlook["model_fingerprint"],
                              "rules_hash":manifest["rules_hash"],"price_fetched_at":cache["fetched_at"]}
                    c.execute("""INSERT OR IGNORE INTO experiment_predictions
                        (experiment_id,captured_at,session,month,horizon,entry,probability,trend,frequency,production,inputs_hash,inputs_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(EXPERIMENT_ID,cutoff.isoformat(),points[-1][0],local.strftime("%Y-%m"),p["horizon_days"],points[-1][1],p["probability"],p["trend"],p["frequency"],probability,_hash(inputs),json.dumps(inputs,allow_nan=False)))
            if fresh:
                for row in c.execute("SELECT * FROM experiment_predictions WHERE experiment_id=?", (EXPERIMENT_ID,)).fetchall():
                    future = [p for p in points if p[0] > row["session"]]
                    if len(future) >= row["horizon"]:
                        day,price = future[row["horizon"]-1]
                        # Datos nuevos no pueden liquidar predicciones emitidas después de ese día.
                        c.execute("INSERT OR IGNORE INTO experiment_outcomes VALUES (?,?,?,?)",(row["id"],day,price,int(price>row["entry"])))
            c.commit()
        saved = experiment_summary(db_path=db_path, cutoff=cutoff)
        return {**saved,"preview":previews,"capture_note":view["capture_note"],
                "price_as_of":view["price_as_of"],"price_status":view["price_status"]}
    return view


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Experimento manual tendencia–frecuencia")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--prepare-prices", action="store_true")
    args = parser.parse_args()
    if args.register:
        from gold_backtest import load_gold_backtest_report
        manifest = register_experiment(load_gold_backtest_report())
        print("Registro congelado:",manifest["id"],manifest["registered_at"])
    if args.prepare_prices:
        cache = load_prices(refresh=True)
        print("Histórico diario:",cache.get("status"),len(cache.get("points",[])),"sesiones")
    print(json.dumps(experiment_summary(),ensure_ascii=False))
