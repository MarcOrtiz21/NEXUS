"""
Motor de rotación sectorial/temática de NEXUS.

Traduce proxies ETF en una lectura legible: qué liderazgos descansan y
qué sectores rezagados están recibiendo flujo.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


ROTATION_THEMES = [
    {
        "ticker": "AIQ",
        "group": "Líderes en descanso",
        "theme": "Infraestructura IA",
        "represents": "nube, centros de datos, software y hardware ligados a IA",
    },
    {
        "ticker": "SMH",
        "group": "Líderes en descanso",
        "theme": "Semiconductores/chips",
        "represents": "Nvidia, AMD, Broadcom, TSMC y fabricantes de chips",
    },
    {
        "ticker": "XLK",
        "group": "Líderes en descanso",
        "theme": "Tecnología grande",
        "represents": "mega caps tech, software, hardware y plataformas",
    },
    {
        "ticker": "XBI",
        "group": "Receptores de flujo",
        "theme": "Biotecnología",
        "represents": "biotech de alto beta, innovación médica y rezagados de salud",
    },
    {
        "ticker": "XLV",
        "group": "Receptores de flujo",
        "theme": "Salud/farmacéuticas",
        "represents": "healthcare defensivo, pharma grande y servicios médicos",
    },
    {
        "ticker": "KIE",
        "group": "Receptores de flujo",
        "theme": "Seguros",
        "represents": "aseguradoras y financieras defensivas sensibles a tipos",
    },
    {
        "ticker": "PJP",
        "group": "Receptores de flujo",
        "theme": "Farmacéuticas",
        "represents": "pharma especializada y compañías de medicamentos",
    },
]


@dataclass
class RotationTheme:
    ticker: str
    group: str
    theme: str
    represents: str
    signal: str
    score: int
    momentum_1m: float | None
    momentum_3m: float | None
    relative_1m_vs_spy: float | None
    trend: str


@dataclass
class RotationResult:
    state: str
    summary: str
    leaders_avg_1m: float | None
    receivers_avg_1m: float | None
    themes: List[RotationTheme]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["themes"] = [asdict(theme) for theme in self.themes]
        return data


class RotationEngine:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.rotation_assets = data.get("RotationAssets", {})
        self.spy_metrics = data.get("Assets", {}).get("SPY", {})

    def evaluate(self) -> RotationResult:
        themes = [self._evaluate_theme(config) for config in ROTATION_THEMES]
        leaders = [t for t in themes if t.group == "Líderes en descanso" and t.momentum_1m is not None]
        receivers = [t for t in themes if t.group == "Receptores de flujo" and t.momentum_1m is not None]

        leaders_avg = self._avg([t.momentum_1m for t in leaders])
        receivers_avg = self._avg([t.momentum_1m for t in receivers])
        state, summary = self._state_and_summary(themes, leaders_avg, receivers_avg)

        return RotationResult(
            state=state,
            summary=summary,
            leaders_avg_1m=leaders_avg,
            receivers_avg_1m=receivers_avg,
            themes=themes,
        )

    def _evaluate_theme(self, config: Dict[str, str]) -> RotationTheme:
        ticker = config["ticker"]
        metrics = self.rotation_assets.get(ticker, {})
        mom_1m = metrics.get("momentum_1m")
        mom_3m = metrics.get("momentum_3m")
        spy_1m = self.spy_metrics.get("momentum_1m")
        relative = mom_1m - spy_1m if mom_1m is not None and spy_1m is not None else None
        trend = self._trend_label(metrics)
        score = self._theme_score(metrics, relative)
        signal = self._signal(config["group"], mom_1m, mom_3m, relative, trend)

        return RotationTheme(
            ticker=ticker,
            group=config["group"],
            theme=config["theme"],
            represents=config["represents"],
            signal=signal,
            score=score,
            momentum_1m=mom_1m,
            momentum_3m=mom_3m,
            relative_1m_vs_spy=relative,
            trend=trend,
        )

    def _theme_score(self, metrics: Dict[str, Any], relative: float | None) -> int:
        price = metrics.get("price")
        if price is None:
            return 0

        score = 50
        for ma_key, weight in (("ma20", 8), ("ma50", 10), ("ma200", 8)):
            ma = metrics.get(ma_key)
            if ma is not None:
                score += weight if price > ma else -weight

        for mom_key, weight in (("momentum_1m", 10), ("momentum_3m", 8)):
            momentum = metrics.get(mom_key)
            if momentum is not None:
                score += weight if momentum > 0 else -weight

        if relative is not None:
            if relative > 1:
                score += 8
            elif relative < -1:
                score -= 8

        return max(0, min(100, score))

    def _signal(
        self,
        group: str,
        mom_1m: float | None,
        mom_3m: float | None,
        relative: float | None,
        trend: str,
    ) -> str:
        if mom_1m is None:
            return "Sin datos"

        outperforming = relative is not None and relative > 1
        underperforming = relative is not None and relative < -1

        if group == "Líderes en descanso":
            if mom_1m < 0 and mom_3m is not None and mom_3m > 0:
                return "Descanso sano tras liderazgo"
            if mom_1m < 0 and underperforming:
                return "Corrección activa"
            if trend == "alcista" and mom_1m > 0:
                return "Liderazgo aún fuerte"
            return "Base en formación"

        if mom_1m > 0 and outperforming:
            return "Entrada clara de flujo"
        if mom_1m > 0:
            return "Mejora incipiente"
        if trend == "alcista":
            return "Mantiene estructura"
        return "Aún sin confirmación"

    def _state_and_summary(
        self,
        themes: List[RotationTheme],
        leaders_avg: float | None,
        receivers_avg: float | None,
    ) -> tuple[str, str]:
        if leaders_avg is None or receivers_avg is None:
            return "SIN DATOS", "No hay datos suficientes para evaluar la rotación."

        receiver_flow = sum(
            1 for t in themes
            if t.group == "Receptores de flujo" and t.relative_1m_vs_spy is not None and t.relative_1m_vs_spy > 1
        )
        leaders_resting = sum(
            1 for t in themes
            if t.group == "Líderes en descanso" and t.momentum_1m is not None and t.momentum_1m < 0
        )

        if receiver_flow >= 2 and leaders_resting >= 1:
            return (
                "ROTACIÓN ACTIVA Y SANA",
                "El dinero descansa parcialmente en IA/semis/tech y busca rezagados como biotech, salud o seguros.",
            )
        if receiver_flow >= 2:
            return (
                "ROTACIÓN HACIA REZAGADOS",
                "Los receptores empiezan a batir al mercado, aunque los líderes no han corregido con claridad.",
            )
        if leaders_resting >= 2 and receivers_avg <= 0:
            return (
                "DESCANSO SIN RELEVO CLARO",
                "Los líderes corrigen, pero todavía no aparece un grupo receptor suficientemente fuerte.",
            )
        if leaders_avg > receivers_avg:
            return (
                "LIDERAZGO TECH DOMINANTE",
                "IA, semiconductores y tecnología siguen mandando; la rotación hacia rezagados no está confirmada.",
            )
        return (
            "ROTACIÓN EN DESARROLLO",
            "Hay señales mixtas: conviene vigilar si los receptores sostienen momentum relativo.",
        )

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

    def _avg(self, values: List[float | None]) -> float | None:
        clean = [value for value in values if value is not None]
        if not clean:
            return None
        return sum(clean) / len(clean)
