"""Perspectiva mensual explicable del oro.

Esta capa no concede permiso operativo. Agrupa factores correlacionados para
que varias expresiones del mismo impulso macro no se contabilicen como votos
independientes. La versión v1 es heurística y su confianza nunca es alta hasta
que exista una validación walk-forward suficiente.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


MODEL_VERSION = "gold-outlook-v2"
PRIVATE_SOURCES_STATUS = "STANDBY"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _fmt(value: float | None, suffix: str = "", digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


def _detail(
    label: str,
    value: float | None,
    *,
    unit: str = "%",
    digits: int = 2,
    source: str | None = None,
    as_of: str | None = None,
    quality: str | None = None,
) -> dict[str, Any]:
    payload = {
        "label": label,
        "value": value,
        "unit": unit,
        "display": _fmt(value, unit, digits),
        "available": value is not None,
    }
    if source:
        payload["source"] = source
    if as_of:
        payload["as_of"] = as_of
    if quality:
        payload["quality"] = quality
    return payload


def _provenance(data: dict[str, Any], key: str) -> dict[str, str]:
    quality_map = data.get("DataQuality") if isinstance(data.get("DataQuality"), dict) else {}
    item = quality_map.get(key) if isinstance(quality_map.get(key), dict) else {}
    payload: dict[str, str] = {}
    source = item.get("source")
    as_of = item.get("as_of") or item.get("captured_at")
    quality = item.get("status")
    if source:
        payload["source"] = str(source)
    if as_of:
        payload["as_of"] = str(as_of)
    if quality:
        payload["quality"] = str(quality)
    return payload


def _metric_detail(
    data: dict[str, Any],
    key: str,
    label: str,
    *,
    unit: str = "%",
    digits: int = 2,
) -> dict[str, Any]:
    return _detail(
        label,
        _number(data.get(key)),
        unit=unit,
        digits=digits,
        **_provenance(data, key),
    )


def _group(
    key: str,
    label: str,
    short_signal: float | None,
    medium_signal: float | None,
    short_weight: float,
    medium_weight: float,
    details: list[dict[str, Any]],
    note: str,
    *,
    score_enabled: bool = True,
) -> dict[str, Any]:
    available = any(item.get("available") for item in details)
    short = _clip(short_signal) if short_signal is not None and available else None
    medium = _clip(medium_signal) if medium_signal is not None and available else None
    detail_available = sum(1 for item in details if item.get("available"))
    effective_short_weight = short_weight if score_enabled else 0.0
    effective_medium_weight = medium_weight if score_enabled else 0.0
    return {
        "id": key,
        "label": label,
        "available": available,
        "coverage_pct": round(detail_available / len(details) * 100, 1) if details else 0.0,
        "short_signal": short,
        "medium_signal": medium,
        "score_enabled": score_enabled,
        "short_weight": effective_short_weight,
        "medium_weight": effective_medium_weight,
        "short_contribution": round(short * effective_short_weight * 100, 2) if short is not None and score_enabled else None,
        "medium_contribution": round(medium * effective_medium_weight * 100, 2) if medium is not None and score_enabled else None,
        "details": details,
        "note": note,
    }


def _trend_signal(metrics: dict[str, Any]) -> float | None:
    price = _number(metrics.get("price"))
    ma20 = _number(metrics.get("ma20"))
    ma50 = _number(metrics.get("ma50"))
    momentum = _number(metrics.get("momentum_1m"))
    parts: list[float] = []
    if price is not None and ma20 is not None:
        parts.append(_clip((price / ma20 - 1) / 0.04))
    if price is not None and ma50 is not None:
        parts.append(_clip((price / ma50 - 1) / 0.08))
    if momentum is not None:
        parts.append(_clip(momentum / 6.0))
    return _mean(parts)


def _latest_as_of(data: dict[str, Any]) -> str | None:
    candidates = []
    for key, value in data.items():
        if not key.endswith("_AsOf") or not isinstance(value, str):
            continue
        try:
            candidates.append((datetime.fromisoformat(value.replace("Z", "+00:00")), value))
        except ValueError:
            continue
    return max(candidates, default=(None, None), key=lambda item: item[0] or datetime.min)[1]


def _horizon(groups: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    signal_key = f"{horizon}_signal"
    weight_key = f"{horizon}_weight"
    contribution_key = f"{horizon}_contribution"
    available = [
        group for group in groups
        if group.get(signal_key) is not None and float(group.get(weight_key) or 0) > 0
    ]
    available_weight = sum(float(group[weight_key]) for group in available)
    raw = (
        sum(float(group[signal_key]) * float(group[weight_key]) for group in available) / available_weight
        if available_weight
        else 0.0
    )
    score = round(_clip(raw) * 100, 1)
    probability = round(_clip(50 + raw * 35, 15, 85), 1)
    if probability >= 60:
        label, tone = "ALCISTA", "GOOD"
    elif probability <= 40:
        label, tone = "BAJISTA", "BAD"
    else:
        label, tone = "NEUTRAL", "WARN"

    total_weight = sum(float(group[weight_key]) for group in groups)
    coverage = round(available_weight / total_weight * 100, 1) if total_weight else 0.0
    confidence = "MEDIA" if coverage >= 70 and abs(probability - 50) >= 8 else "BAJA"
    drivers = sorted(
        (
            {
                "id": group["id"],
                "label": group["label"],
                "contribution": group[contribution_key],
                "note": group["note"],
            }
            for group in available
        ),
        key=lambda item: abs(float(item["contribution"] or 0)),
        reverse=True,
    )
    return {
        "horizon_days": 21 if horizon == "short" else 63,
        "label": label,
        "tone": tone,
        "probability_up": probability,
        "score": score,
        "confidence": confidence,
        "coverage_pct": coverage,
        "drivers": drivers[:5],
    }


def build_gold_outlook(
    data: dict[str, Any] | None,
    gld_metrics: dict[str, Any] | None = None,
    uup_metrics: dict[str, Any] | None = None,
    *,
    include_positioning_in_score: bool | None = None,
) -> dict[str, Any]:
    """Construye una perspectiva agrupada sin tratar ausencias como ceros."""
    data = data or {}
    gld_metrics = gld_metrics or {}
    uup_metrics = uup_metrics or {}

    cpi_mom = _number(data.get("CPI_MoM_Pct"))
    core_cpi_mom = _number(data.get("Core_CPI_MoM_Pct"))
    pce_mom = _number(data.get("PCE_MoM_Pct"))
    core_pce_mom = _number(data.get("Core_PCE_MoM_Pct"))
    cpi_3m = _number(data.get("CPI_3M_Annualized_Pct"))
    core_cpi_3m = _number(data.get("Core_CPI_3M_Annualized_Pct"))
    pce_3m = _number(data.get("PCE_3M_Annualized_Pct"))
    core_pce_3m = _number(data.get("Core_PCE_3M_Annualized_Pct"))
    cpi_yoy = _number(data.get("CPI_YoY_Pct"))
    core_cpi_yoy = _number(data.get("Core_CPI_YoY_Pct"))
    pce_yoy = _number(data.get("PCE_YoY_Pct"))
    core_pce_yoy = _number(data.get("Core_PCE_YoY_Pct"))
    monthly_inflation = _mean([cpi_mom, core_cpi_mom, pce_mom, core_pce_mom])
    three_month_inflation = _mean([cpi_3m, core_cpi_3m, pce_3m, core_pce_3m])
    yearly_inflation = _mean([cpi_yoy, core_cpi_yoy, pce_yoy, core_pce_yoy])
    monthly_pressure = _clip((monthly_inflation - 0.20) / 0.30) if monthly_inflation is not None else None
    three_month_pressure = _clip((three_month_inflation - 2.4) / 3.0) if three_month_inflation is not None else None
    yearly_pressure = _clip((yearly_inflation - 2.0) / 2.0) if yearly_inflation is not None else None
    inflation_short = _mean([
        -monthly_pressure if monthly_pressure is not None else None,
        -0.70 * three_month_pressure if three_month_pressure is not None else None,
        -0.35 * yearly_pressure if yearly_pressure is not None else None,
    ])
    inflation_medium = _mean([
        0.35 * monthly_pressure if monthly_pressure is not None else None,
        0.60 * three_month_pressure if three_month_pressure is not None else None,
        0.55 * yearly_pressure if yearly_pressure is not None else None,
    ])

    real_yield = _number(data.get("Real_Yield_10Y_Pct"))
    real_yield_change = _number(data.get("Real_Yield_10Y_1M_Change_Pp"))
    breakeven = _number(data.get("Breakeven_10Y_Pct"))
    breakeven_change = _number(data.get("Breakeven_10Y_1M_Change_Pp"))
    rates_signal = _mean([
        _clip(-(real_yield - 1.5) / 1.5) if real_yield is not None else None,
        _clip(-real_yield_change / 0.40) if real_yield_change is not None else None,
    ])

    usd_momentum = _number(uup_metrics.get("momentum_1m"))
    dollar_signal = _clip(-usd_momentum / 4.0) if usd_momentum is not None else None

    wti_change = _number(data.get("WTI_1M_Change_Pct"))
    energy_mom = _number(data.get("Energy_CPI_MoM_Pct"))
    energy_yoy = _number(data.get("Energy_CPI_YoY_Pct"))
    energy_pressure = _mean([
        _clip(wti_change / 12.0) if wti_change is not None else None,
        _clip(energy_mom / 2.0) if energy_mom is not None else None,
        _clip(energy_yoy / 15.0) if energy_yoy is not None else None,
    ])
    energy_short = -0.25 * energy_pressure if energy_pressure is not None else None
    energy_medium = 0.55 * energy_pressure if energy_pressure is not None else None

    unemployment_change = _number(data.get("Unemployment_1M_Change_Pp"))
    payroll_change = _number(data.get("Payrolls_1M_Change_Thousands"))
    industrial_mom = _number(data.get("Industrial_Production_MoM_Pct"))
    activity_signal = _mean([
        _clip(unemployment_change / 0.30) if unemployment_change is not None else None,
        _clip(-(payroll_change - 100.0) / 250.0) if payroll_change is not None else None,
        _clip(-industrial_mom / 0.80) if industrial_mom is not None else None,
    ])

    m2_change = _number(data.get("M2_Change_Pct"))
    liquidity_signal = _clip(m2_change / 3.0) if m2_change is not None else None
    vix = _number(data.get("VIX"))
    risk_signal = _clip((vix - 18.0) / 15.0) if vix is not None else None
    technical_signal = _trend_signal(gld_metrics)
    central_bank_tonnes = _number(data.get("Central_Bank_Net_Purchases_Tonnes"))
    official_signal = _clip(central_bank_tonnes / 100.0) if central_bank_tonnes is not None else None

    cftc_weekly = _number(data.get("CFTC_MM_Weekly_Change_Contracts"))
    cftc_four_week = _number(data.get("CFTC_MM_4W_Change_Contracts"))
    cftc_percentile = _number(data.get("CFTC_MM_Percentile_3Y"))
    cftc_divergence = _number(data.get("CFTC_Price_Positioning_Divergence"))
    positioning_trend = _mean([
        _clip(cftc_weekly / 30_000.0) if cftc_weekly is not None else None,
        _clip(cftc_four_week / 80_000.0) if cftc_four_week is not None else None,
    ])
    positioning_crowding = (
        -0.45 * _clip((cftc_percentile - 50.0) / 35.0)
        if cftc_percentile is not None else None
    )
    positioning_short = _mean([
        0.65 * positioning_trend if positioning_trend is not None else None,
        positioning_crowding,
        0.30 * cftc_divergence if cftc_divergence is not None else None,
    ])
    positioning_medium = _mean([
        0.40 * positioning_trend if positioning_trend is not None else None,
        positioning_crowding,
        0.20 * cftc_divergence if cftc_divergence is not None else None,
    ])
    positioning_enabled = (
        bool(data.get("CFTC_Positioning_Model_Eligible"))
        if include_positioning_in_score is None else include_positioning_in_score
    )

    groups = [
        _group(
            "inflation", "Inflación", inflation_short, inflation_medium, 0.14, 0.16,
            [
                _metric_detail(data, "CPI_MoM_Pct", "CPI mensual"),
                _metric_detail(data, "CPI_3M_Annualized_Pct", "CPI 3M anualizado"),
                _metric_detail(data, "CPI_YoY_Pct", "CPI interanual"),
                _metric_detail(data, "Core_CPI_MoM_Pct", "CPI subyacente mensual"),
                _metric_detail(data, "Core_CPI_3M_Annualized_Pct", "CPI subyacente 3M anualizado"),
                _metric_detail(data, "Core_CPI_YoY_Pct", "CPI subyacente interanual"),
                _metric_detail(data, "PCE_MoM_Pct", "PCE mensual"),
                _metric_detail(data, "PCE_3M_Annualized_Pct", "PCE 3M anualizado"),
                _metric_detail(data, "PCE_YoY_Pct", "PCE interanual"),
                _metric_detail(data, "Core_PCE_MoM_Pct", "PCE subyacente mensual"),
                _metric_detail(data, "Core_PCE_3M_Annualized_Pct", "PCE subyacente 3M anualizado"),
                _metric_detail(data, "Core_PCE_YoY_Pct", "PCE subyacente interanual"),
            ],
            "Una sola familia: mensual, aceleración 3M e interanual describen el mismo impulso y no cuentan como votos separados.",
        ),
        _group(
            "real_rates", "Tipos reales y expectativas", rates_signal, rates_signal, 0.22, 0.18,
            [
                _metric_detail(data, "Real_Yield_10Y_Pct", "TIPS real 10Y"),
                _metric_detail(data, "Real_Yield_10Y_1M_Change_Pp", "Cambio TIPS 1M", unit=" pp"),
                _metric_detail(data, "Breakeven_10Y_Pct", "Breakeven 10Y"),
                _metric_detail(data, "Breakeven_10Y_1M_Change_Pp", "Cambio breakeven 1M", unit=" pp"),
            ],
            "La señal usa TIPS reales; el breakeven se muestra como contexto para no duplicar inflación.",
        ),
        _group(
            "dollar", "Dólar", dollar_signal, dollar_signal, 0.18, 0.12,
            [_detail("Momentum UUP 1M", usd_momentum, **_provenance(data, "Assets.UUP"))],
            "El dólar se contabiliza una sola vez aunque también afecte a tipos y materias primas.",
        ),
        _group(
            "energy", "Energía", energy_short, energy_medium, 0.06, 0.08,
            [
                _metric_detail(data, "WTI_1M_Change_Pct", "WTI 1M"),
                _metric_detail(data, "Energy_CPI_MoM_Pct", "CPI energía mensual"),
                _metric_detail(data, "Energy_CPI_YoY_Pct", "CPI energía interanual"),
            ],
            "Canal indirecto y limitado: energía influye en inflación, expectativas y política monetaria.",
        ),
        _group(
            "activity", "Actividad económica", activity_signal, activity_signal, 0.10, 0.10,
            [
                _metric_detail(data, "Unemployment_1M_Change_Pp", "Cambio desempleo", unit=" pp"),
                _metric_detail(data, "Payrolls_1M_Change_Thousands", "Nóminas mensuales", unit=" mil", digits=0),
                _metric_detail(data, "Industrial_Production_MoM_Pct", "Producción industrial mensual"),
            ],
            "Debilidad de empleo o industria puede favorecer refugio; la familia tiene un único límite.",
        ),
        _group(
            "liquidity", "Liquidez", liquidity_signal, liquidity_signal, 0.06, 0.10,
            [_metric_detail(data, "M2_Change_Pct", "Variación M2")],
            "La expansión monetaria se trata como contexto, no como señal aislada.",
        ),
        _group(
            "risk", "Riesgo", risk_signal, 0.65 * risk_signal if risk_signal is not None else None, 0.10, 0.05,
            [_detail("VIX", vix, unit="", digits=1, **_provenance(data, "VIX"))],
            "El estrés favorece demanda defensiva principalmente en el horizonte corto.",
        ),
        _group(
            "technical", "Técnica del oro", technical_signal, 0.75 * technical_signal if technical_signal is not None else None, 0.14, 0.09,
            [
                _detail("Precio GLD", _number(gld_metrics.get("price")), unit="", digits=2, **_provenance(data, "Assets.GLD")),
                _detail("Momentum GLD 1M", _number(gld_metrics.get("momentum_1m")), **_provenance(data, "Assets.GLD")),
            ],
            "Solo usa información disponible en la captura; nunca el resultado futuro del propio oro.",
        ),
        _group(
            "positioning", "Posicionamiento especulativo", positioning_short, positioning_medium, 0.08, 0.10,
            [
                _metric_detail(data, "CFTC_MM_Net_Contracts", "Managed Money neto", unit=" contratos", digits=0),
                _metric_detail(data, "CFTC_MM_Net_Pct_OI", "Neto / interés abierto", unit="%"),
                _metric_detail(data, "CFTC_MM_Weekly_Change_Contracts", "Cambio semanal", unit=" contratos", digits=0),
                _metric_detail(data, "CFTC_MM_4W_Change_Contracts", "Cambio 4 semanas", unit=" contratos", digits=0),
                _metric_detail(data, "CFTC_MM_Percentile_3Y", "Percentil 3 años", unit="%", digits=1),
                _metric_detail(data, "CFTC_MM_ZScore_3Y", "Z-score 3 años", unit="", digits=2),
                _metric_detail(data, "CFTC_Concentration_4_Long_Pct", "Concentración 4 mayores · largo", unit="%", digits=1),
                _metric_detail(data, "CFTC_Concentration_4_Short_Pct", "Concentración 4 mayores · corto", unit="%", digits=1),
            ],
            (
                "CFTC Managed Money: combina cambio y saturación extrema en una única familia limitada."
                if positioning_enabled else
                "Visible como contexto; no puntúa hasta demostrar mejora estable fuera de muestra."
            ),
            score_enabled=positioning_enabled,
        ),
        _group(
            "official_demand", "Demanda oficial", official_signal, official_signal, 0.00, 0.12,
            [_detail("Compras netas", central_bank_tonnes, unit=" t", digits=1)],
            "Pendiente de una fuente pública/licenciada estable; no se sustituyen ausencias por votos positivos.",
        ),
    ]

    return {
        "version": MODEL_VERSION,
        "status": "PRELIMINARY",
        "as_of": _latest_as_of(data),
        "private_sources_status": PRIVATE_SOURCES_STATUS,
        "methodology": "Perspectiva heurística agrupada; no es una orden y el modelo sigue en fase preliminar.",
        "short_term": _horizon(groups, "short"),
        "medium_term": _horizon(groups, "medium"),
        "groups": groups,
        "data_notes": [
            "Los consensos privados permanecen en standby; esta versión usa datos públicos observados.",
            "El backtest point-in-time está completado, pero aún no supera de forma consistente las referencias; la confianza permanece limitada.",
            (
                "El posicionamiento CFTC ha superado la puerta de ablación y aporta con peso limitado."
                if positioning_enabled else
                "El posicionamiento CFTC se muestra, pero su peso permanece desactivado hasta superar la ablación fuera de muestra."
            ),
            "Demanda oficial y flujos ETF no aportan score mientras falte una fuente verificable.",
        ],
        "what_changes_signal": [
            "Una caída sostenida de TIPS reales y del dólar mejoraría la lectura.",
            "Una subida conjunta de tipos reales y dólar deterioraría ambos horizontes.",
            "La inflación mensual se reevalúa junto a tipos: nunca funciona como voto independiente.",
            "Un giro del posicionamiento CFTC, especialmente desde un extremo, puede confirmar o debilitar la lectura.",
        ],
    }
