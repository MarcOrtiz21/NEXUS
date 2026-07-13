"""
Capa de decisión multi-activo de NEXUS.

Convierte las señales del motor lógico y los datos de mercado en una
conclusión operativa trazable: acción, score, confianza y asignación.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from logic_engine import MarketStatus


ASSET_LABELS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "TLT": "Bonos largos",
    "GLD": "Oro",
    "UUP": "Dólar",
    "CASH": "Liquidez",
}

REQUIRED_INPUTS = {
    "VIX": "VIX",
    "US10Y": "Bono 10Y",
    "Assets.SPY.price": "precio SPY",
    "Assets.QQQ.price": "precio QQQ",
}


@dataclass
class DecisionResult:
    action: str
    score: int
    confidence: str
    favored_assets: List[str]
    allocation: Dict[str, int]
    asset_scores: Dict[str, Dict[str, Any]]
    rationale: str
    inputs_used: List[str]
    missing_inputs: List[str]
    macro_action: str = "ESPERAR"
    operational_action: str = "ESPERAR"
    operational_pause_reason: str | None = None
    macro_allocation: Dict[str, int] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionEngine:
    """Genera una decisión final a partir de datos y estado de mercado."""

    def __init__(self, data: Dict[str, Any], status: MarketStatus, alerts: List[str]):
        self.data = data
        self.status = status
        self.alerts = alerts

    def evaluate(self) -> DecisionResult:
        missing = self._missing_required_inputs()
        inputs_used = self._inputs_used()

        if missing:
            return DecisionResult(
                action="DATOS INSUFICIENTES",
                score=0,
                confidence="BAJA",
                favored_assets=["Liquidez"],
                allocation={"SPY": 0, "QQQ": 0, "TLT": 0, "GLD": 0, "UUP": 0, "CASH": 100},
                asset_scores=self._asset_scores(0),
                rationale="No se emite señal operativa porque faltan datos críticos: " + ", ".join(missing) + ".",
                inputs_used=inputs_used,
                missing_inputs=missing,
                macro_action="DATOS INSUFICIENTES",
                operational_action="DATOS INSUFICIENTES",
                operational_pause_reason="Datos críticos incompletos",
                macro_allocation={"SPY": 0, "QQQ": 0, "TLT": 0, "GLD": 0, "UUP": 0, "CASH": 100},
            )

        score, reasons = self._macro_score()
        score = max(0, min(100, score))
        asset_scores = self._asset_scores(score)
        macro_allocation = self._build_allocation(score, asset_scores)
        macro_action = self._action_from_score(score)
        macro_confidence = self._confidence(score)

        allocation = dict(macro_allocation)
        favored_assets = self._favored_assets(allocation)
        action = macro_action
        confidence = macro_confidence
        operational_pause_reason = None

        if self.status == MarketStatus.BLOCKED:
            operational_pause_reason = "Filtro de riesgo activo (calendario macro US o sentimiento extremo)"
            action = "ESPERAR"
            confidence = "MEDIA"
            allocation = {"SPY": 0, "QQQ": 0, "TLT": 20, "GLD": 20, "UUP": 10, "CASH": 50}
            favored_assets = self._favored_assets(allocation)
            reasons.insert(0, "la señal operativa está pausada por un filtro de riesgo")
        elif self.status == MarketStatus.PANIC:
            operational_pause_reason = "Entorno de pánico o estrés extremo detectado por el motor lógico"
            action = "REDUCIR RIESGO"
            confidence = "ALTA"
            allocation = {"SPY": 5, "QQQ": 0, "TLT": 20, "GLD": 20, "UUP": 10, "CASH": 45}
            favored_assets = self._favored_assets(allocation)
            reasons.insert(0, "el motor lógico detecta pánico o estrés extremo")

        return DecisionResult(
            action=action,
            score=score,
            confidence=confidence,
            favored_assets=favored_assets,
            allocation=allocation,
            asset_scores=asset_scores,
            rationale=self._build_rationale(reasons),
            inputs_used=inputs_used,
            missing_inputs=[],
            macro_action=macro_action,
            operational_action=action,
            operational_pause_reason=operational_pause_reason,
            macro_allocation=macro_allocation,
        )

    def _missing_required_inputs(self) -> List[str]:
        missing = []
        assets = self.data.get("Assets", {})
        for key, label in REQUIRED_INPUTS.items():
            if key.startswith("Assets."):
                _, asset, metric = key.split(".")
                if assets.get(asset, {}).get(metric) is None:
                    missing.append(label)
            elif self.data.get(key) is None:
                missing.append(label)
        return missing

    def _inputs_used(self) -> List[str]:
        used = []
        for key, label in {
            "VIX": "VIX",
            "US10Y": "Bono 10Y",
            "Correlation_Proxy": "correlación sectorial",
            "PE_Forward": "PER forward",
            "PE_Trailing": "PER trailing",
            "M2_Change_Pct": "liquidez M2",
            "CPI_YoY_Pct": "IPC interanual",
        }.items():
            if self.data.get(key) is not None:
                used.append(label)

        for asset, metrics in self.data.get("Assets", {}).items():
            if metrics.get("price") is not None:
                used.append(ASSET_LABELS.get(asset, asset))
        return used

    def _macro_score(self) -> tuple[int, List[str]]:
        score = 50
        reasons: List[str] = []

        vix = self.data.get("VIX")
        if vix < 16:
            score += 12
            reasons.append("VIX contenido")
        elif vix < 25:
            score += 4
            reasons.append("VIX en zona normal")
        elif vix < 30:
            score -= 15
            reasons.append("VIX elevado")
        else:
            score -= 35
            reasons.append("VIX en zona de pánico")

        corr = self.data.get("Correlation_Proxy")
        if corr is not None:
            abs_corr = abs(corr)
            if abs_corr < 0.3:
                score += 8
                reasons.append("correlación sectorial baja")
            elif abs_corr > 0.6:
                score -= 18
                reasons.append("correlación sectorial alta")
            else:
                score -= 4
                reasons.append("correlación sectorial moderada")

        us10y = self.data.get("US10Y")
        if us10y < 4.0:
            score += 8
            reasons.append("tipos largos benignos")
        elif us10y < 4.5:
            reasons.append("bono 10Y estable")
        elif us10y < 5.0:
            score -= 8
            reasons.append("tipos cerca de zona de presión")
        else:
            score -= 18
            reasons.append("tipos en zona restrictiva")

        m2_chg = self.data.get("M2_Change_Pct")
        if m2_chg is not None:
            if m2_chg > 1.0:
                score += 10
                reasons.append("liquidez M2 expansiva")
            elif m2_chg < -1.0:
                score -= 12
                reasons.append("liquidez M2 contractiva")
            else:
                score += 2
                reasons.append("liquidez M2 estable")

        cpi_yoy = self.data.get("CPI_YoY_Pct")
        if cpi_yoy is not None:
            if cpi_yoy < 3.0:
                score += 8
                reasons.append("inflación controlada")
            elif cpi_yoy <= 4.0:
                score -= 4
                reasons.append("inflación pegajosa")
            else:
                score -= 12
                reasons.append("inflación alta")

        pe_fwd = self.data.get("PE_Forward")
        pe_trail = self.data.get("PE_Trailing")
        if pe_fwd is not None:
            if pe_fwd < 18:
                score += 6
                reasons.append("PER forward atractivo")
            elif pe_fwd > 25:
                score -= 8
                reasons.append("PER forward exigente")
        elif pe_trail is not None and pe_trail > 28:
            score -= 5
            reasons.append("PER trailing exigente")

        assets = self.data.get("Assets", {})
        spy_score = self._asset_trend_score(assets.get("SPY", {}))
        qqq_score = self._asset_trend_score(assets.get("QQQ", {}))
        if spy_score is not None and qqq_score is not None:
            momentum_adjustment = round(((spy_score + qqq_score) / 2 - 50) * 0.25)
            score += momentum_adjustment
            if momentum_adjustment > 3:
                reasons.append("momentum positivo en SPY y Nasdaq")
            elif momentum_adjustment < -3:
                reasons.append("momentum débil en SPY y Nasdaq")

        if self.status == MarketStatus.CAUTION:
            score -= 10
            reasons.append("el motor lógico pide precaución")
        elif self.status == MarketStatus.HEALTHY:
            score += 5
            reasons.append("el motor lógico confirma entorno saludable")

        sentiment_text = " ".join(self.alerts).lower()
        if "sentimiento" in sentiment_text and "optimismo" in sentiment_text:
            score += 4
            reasons.append("sentimiento de noticias favorable")
        elif "sentimiento" in sentiment_text and ("miedo" in sentiment_text or "mixto" in sentiment_text):
            score -= 4
            reasons.append("sentimiento de noticias prudente")

        return score, reasons

    def _asset_trend_score(self, metrics: Dict[str, Any]) -> int | None:
        price = metrics.get("price")
        if price is None:
            return None

        score = 50
        for ma_key, weight in (("ma20", 5), ("ma50", 7), ("ma200", 8)):
            ma = metrics.get(ma_key)
            if ma is None:
                continue
            score += weight if price > ma else -weight

        for mom_key, weight in (("momentum_1m", 6), ("momentum_3m", 8)):
            momentum = metrics.get(mom_key)
            if momentum is None:
                continue
            score += weight if momentum > 0 else -weight

        volatility = metrics.get("volatility_20d")
        if volatility is not None:
            if volatility < 18:
                score += 3
            elif volatility > 30:
                score -= 5

        return max(0, min(100, score))

    def _asset_scores(self, macro_score: int) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        assets = self.data.get("Assets", {})
        defensive_boost = max(0, 60 - macro_score)
        risk_boost = max(0, macro_score - 50)

        for asset in ["SPY", "QQQ", "TLT", "GLD", "UUP"]:
            trend_score = self._asset_trend_score(assets.get(asset, {}))
            if trend_score is None:
                result[asset] = {
                    "label": ASSET_LABELS[asset],
                    "score": 0,
                    "action": "SIN DATOS",
                    "trend": "sin datos",
                    "momentum_1m": None,
                    "momentum_3m": None,
                    "volatility_20d": None,
                }
                continue

            if asset in ("SPY", "QQQ"):
                score = round(trend_score * 0.65 + macro_score * 0.35 + risk_boost * 0.15)
            elif asset in ("TLT", "GLD"):
                score = round(trend_score * 0.55 + (100 - macro_score) * 0.25 + defensive_boost * 0.2)
            else:
                score = round(trend_score * 0.45 + defensive_boost * 0.4)

            score = max(0, min(100, score))
            metrics = assets.get(asset, {})
            result[asset] = {
                "label": ASSET_LABELS[asset],
                "score": score,
                "action": self._action_from_score(score),
                "trend": self._trend_label(metrics),
                "momentum_1m": metrics.get("momentum_1m"),
                "momentum_3m": metrics.get("momentum_3m"),
                "volatility_20d": metrics.get("volatility_20d"),
            }

        cash_score = max(20, min(100, 100 - macro_score + defensive_boost))
        result["CASH"] = {
            "label": ASSET_LABELS["CASH"],
            "score": cash_score,
            "action": "AUMENTAR" if cash_score >= 60 else ("MANTENER" if cash_score >= 35 else "REDUCIR"),
            "trend": "defensivo",
            "momentum_1m": None,
            "momentum_3m": None,
            "volatility_20d": None,
        }
        return result

    def _trend_label(self, metrics: Dict[str, Any]) -> str:
        price = metrics.get("price")
        ma50 = metrics.get("ma50")
        ma200 = metrics.get("ma200")
        if price is None or ma50 is None:
            return "sin datos"
        if ma200 is not None and price > ma50 > ma200:
            return "alcista"
        if ma200 is not None and price < ma50 < ma200:
            return "bajista"
        return "mixta"

    def _build_allocation(self, score: int, asset_scores: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        spy_score = asset_scores.get("SPY", {}).get("score", 50)
        qqq_score = asset_scores.get("QQQ", {}).get("score", 50)

        if score >= 75:
            raw = {"SPY": 35, "QQQ": 30, "TLT": 10, "GLD": 10, "UUP": 0, "CASH": 15}
        elif score >= 60:
            raw = {"SPY": 30, "QQQ": 20, "TLT": 10, "GLD": 10, "UUP": 5, "CASH": 25}
        elif score >= 45:
            raw = {"SPY": 20, "QQQ": 10, "TLT": 15, "GLD": 15, "UUP": 5, "CASH": 35}
        elif score >= 30:
            raw = {"SPY": 10, "QQQ": 5, "TLT": 20, "GLD": 20, "UUP": 10, "CASH": 35}
        else:
            raw = {"SPY": 0, "QQQ": 0, "TLT": 20, "GLD": 20, "UUP": 10, "CASH": 50}

        if qqq_score - spy_score > 10 and raw["QQQ"] > 0:
            raw["QQQ"] += 5
            raw["SPY"] -= 5
        elif spy_score - qqq_score > 10 and raw["SPY"] > 0:
            raw["SPY"] += 5
            raw["QQQ"] = max(0, raw["QQQ"] - 5)

        for asset in ["TLT", "GLD", "UUP"]:
            if asset_scores.get(asset, {}).get("score", 0) >= 70 and raw["CASH"] >= 5:
                raw[asset] += 5
                raw["CASH"] -= 5

        return self._normalize_allocation(raw)

    def _normalize_allocation(self, allocation: Dict[str, int]) -> Dict[str, int]:
        total = sum(allocation.values())
        if total == 100:
            return allocation
        adjusted = {asset: round(weight * 100 / total) for asset, weight in allocation.items()}
        drift = 100 - sum(adjusted.values())
        adjusted["CASH"] += drift
        return adjusted

    def _favored_assets(self, allocation: Dict[str, int]) -> List[str]:
        highest = max(allocation.values())
        return [
            ASSET_LABELS.get(asset, asset)
            for asset, weight in allocation.items()
            if weight == highest and weight > 0
        ]

    def _action_from_score(self, score: int) -> str:
        if score >= 75:
            return "COMPRAR"
        if score >= 60:
            return "COMPRAR PARCIAL"
        if score >= 45:
            return "MANTENER"
        if score >= 30:
            return "ESPERAR"
        return "REDUCIR RIESGO"

    def _confidence(self, score: int) -> str:
        optional_inputs = ["Correlation_Proxy", "M2_Change_Pct", "CPI_YoY_Pct", "PE_Forward"]
        available = sum(1 for key in optional_inputs if self.data.get(key) is not None)
        if available >= 3 and score not in range(45, 60):
            return "ALTA"
        if available >= 2:
            return "MEDIA"
        return "BAJA"

    def _build_rationale(self, reasons: List[str]) -> str:
        if not reasons:
            return "La decisión se basa en las señales disponibles, sin catalizadores dominantes."
        main_reasons = reasons[:5]
        return "La decisión se apoya en " + ", ".join(main_reasons) + "."
