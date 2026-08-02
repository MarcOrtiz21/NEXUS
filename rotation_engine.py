"""
Motor de rotación sectorial/temática de NEXUS.

Traduce proxies ETF en una lectura legible: qué liderazgos descansan y
qué sectores rezagados están recibiendo flujo.
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List

from utils import trend_label
from rotation_catalog import ROTATION_COMPANY_TICKERS, ROTATION_THEME_COMPANIES


ROTATION_THEMES = [
    {
        "ticker": "XLK", "group": "Tecnología", "theme": "Tecnología grande",
        "represents": "mega caps tecnológicas y plataformas",
        "names": ["Apple", "Microsoft", "NVIDIA", "Broadcom", "Oracle"],
        "news_topics": ["IA/tecnología", "Resultados"],
    },
    {
        "ticker": "SMH", "group": "Tecnología", "theme": "Semiconductores",
        "represents": "diseño y fabricación de chips",
        "names": ["NVIDIA", "TSMC", "ASML", "Broadcom", "AMD"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "SOXX", "group": "Tecnología", "theme": "Equipamiento y memorias",
        "represents": "cadena de suministro de semiconductores",
        "names": ["NVIDIA", "Broadcom", "AMD", "Intel", "Qualcomm"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "IGV", "group": "Tecnología", "theme": "Software y diseño",
        "represents": "software empresarial, EDA e IP",
        "names": ["Microsoft", "Salesforce", "Adobe", "Intuit", "Synopsys"],
        "news_topics": ["IA/tecnología", "Resultados"],
    },
    {
        "ticker": "AIQ", "group": "Tecnología", "theme": "Infraestructura IA",
        "represents": "hardware, nube y automatización IA",
        "names": ["NVIDIA", "Microsoft", "Meta", "Amazon", "Alphabet"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "FIVG", "group": "Tecnología", "theme": "Redes",
        "represents": "5G, conectividad y transporte de datos",
        "names": ["Apple", "Cisco", "Qualcomm", "Broadcom", "Ericsson"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "SRVR", "group": "Tecnología", "theme": "Data centers",
        "represents": "infraestructura física digital",
        "names": ["Equinix", "Digital Realty", "American Tower", "Crown Castle"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "GRID", "group": "Tecnología", "theme": "Energía para IA",
        "represents": "red eléctrica e infraestructura energética",
        "names": ["Eaton", "ABB", "Schneider", "Quanta Services", "Hubbell"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "VRT", "group": "Tecnología", "theme": "Refrigeración",
        "represents": "gestión térmica y centros de datos",
        "names": ["Vertiv"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "SKYY", "group": "Tecnología", "theme": "Cloud",
        "represents": "software e infraestructura cloud",
        "names": ["Amazon", "Microsoft", "Oracle", "Salesforce", "ServiceNow"],
        "news_topics": ["IA/tecnología", "Resultados"],
    },
    {
        "ticker": "CIBR", "group": "Tecnología", "theme": "Ciberseguridad",
        "represents": "seguridad digital defensiva",
        "names": ["Crowdstrike", "Palo Alto", "Fortinet", "Zscaler", "Okta"],
        "news_topics": ["IA/tecnología"],
    },
    {
        "ticker": "XLV", "group": "Defensivos", "theme": "Salud",
        "represents": "healthcare, servicios y farmacéuticas",
        "names": ["Eli Lilly", "UnitedHealth", "Johnson & Johnson", "AbbVie", "Merck"],
        "news_topics": ["Resultados"],
    },
    {
        "ticker": "XBI", "group": "Defensivos", "theme": "Biotecnología",
        "represents": "innovación médica de alta volatilidad",
        "names": ["Amgen", "Gilead", "Moderna", "Biogen", "Regeneron"],
        "news_topics": ["Resultados"],
    },
    {
        "ticker": "PJP", "group": "Defensivos", "theme": "Farmacéuticas",
        "represents": "medicamentos y pharma establecida",
        "names": ["Eli Lilly", "Johnson & Johnson", "Pfizer", "Merck", "AbbVie"],
        "news_topics": ["Resultados"],
    },
    {
        "ticker": "KIE", "group": "Financieros", "theme": "Seguros",
        "represents": "aseguradoras sensibles a tipos",
        "names": ["Progressive", "Chubb", "AIG", "Travelers", "MetLife"],
        "news_topics": ["Fed/tipos"],
    },
    {
        "ticker": "KBE", "group": "Financieros", "theme": "Bancos",
        "represents": "banca y curva de tipos",
        "names": ["JPMorgan", "Bank of America", "Wells Fargo", "Citigroup", "US Bancorp"],
        "news_topics": ["Fed/tipos", "Recesión/empleo"],
    },
    {
        "ticker": "XLI", "group": "Cíclicos", "theme": "Industriales",
        "represents": "producción, transporte y maquinaria",
        "names": ["GE", "Caterpillar", "RTX", "Honeywell", "Union Pacific"],
        "news_topics": ["Resultados"],
    },
    {
        "ticker": "ITA", "group": "Cíclicos", "theme": "Defensa",
        "represents": "aeroespacial y defensa",
        "names": ["GE", "RTX", "Boeing", "Lockheed Martin", "Northrop Grumman"],
        "news_topics": ["Geopolítica"],
    },
    {
        "ticker": "XLY", "group": "Cíclicos", "theme": "Consumo discrecional",
        "represents": "consumo no esencial",
        "names": ["Amazon", "Tesla", "Home Depot", "McDonald's", "Nike"],
        "news_topics": ["Resultados", "Recesión/empleo"],
    },
    {
        "ticker": "XLU", "group": "Defensivos", "theme": "Utilities",
        "represents": "servicios públicos",
        "names": ["NextEra", "Southern", "Duke Energy", "Constellation", "American Electric"],
        "news_topics": ["Fed/tipos"],
    },
    {
        "ticker": "XLB", "group": "Cíclicos", "theme": "Materiales",
        "represents": "metales, químicos y materias primas",
        "names": ["Linde", "Sherwin-Williams", "Freeport", "Ecolab", "Air Products"],
        "news_topics": ["Inflación"],
    },
    {
        "ticker": "XLE", "group": "Cíclicos", "theme": "Energía tradicional",
        "represents": "petróleo y gas",
        "names": ["Exxon", "Chevron", "ConocoPhillips", "EOG", "Schlumberger"],
        "news_topics": ["Geopolítica", "Inflación"],
    },
    {
        "ticker": "EWJ", "group": "Asia", "theme": "Japón",
        "represents": "mercado japonés de gran capitalización",
        "names": ["Toyota", "Sony", "Mitsubishi UFJ", "Keyence", "SoftBank"],
        "news_topics": ["Asia", "Geopolítica", "Fed/tipos"],
    },
    {
        "ticker": "FXI", "group": "Asia", "theme": "China",
        "represents": "grandes empresas chinas cotizadas",
        "names": ["Tencent", "Alibaba", "China Construction Bank", "Meituan", "BYD"],
        "news_topics": ["Asia", "Geopolítica"],
    },
    {
        "ticker": "AAXJ", "group": "Asia", "theme": "Asia emergente",
        "represents": "Asia ex-Japón: China, Taiwán, Corea, India",
        "names": ["TSMC", "Tencent", "Samsung", "Alibaba", "Reliance"],
        "news_topics": ["Asia", "Geopolítica", "IA/tecnología"],
    },
    {
        "ticker": "EWY", "group": "Asia", "theme": "Corea del Sur",
        "represents": "exportadores coreanos y semis de memoria",
        "names": ["Samsung", "SK Hynix", "Hyundai", "KB Financial", "POSCO"],
        "news_topics": ["Asia", "IA/tecnología", "Geopolítica"],
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
    price: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    volatility_20d: float | None = None
    names: List[str] = field(default_factory=list)
    news_topics: List[str] = field(default_factory=list)
    companies: List[Dict[str, Any]] = field(default_factory=list)


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
        self.company_metrics = data.get("RotationCompanies", {})
        self.spy_metrics = data.get("Assets", {}).get("SPY", {})

    def evaluate(self) -> RotationResult:
        themes = [self._evaluate_theme(config) for config in ROTATION_THEMES]
        leaders = [t for t in themes if t.group == "Tecnología" and t.momentum_1m is not None]
        receivers = [t for t in themes if t.group != "Tecnología" and t.momentum_1m is not None]

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

    def _evaluate_theme(self, config: Dict[str, Any]) -> RotationTheme:
        ticker = config["ticker"]
        metrics = self.rotation_assets.get(ticker, {})
        mom_1m = metrics.get("momentum_1m")
        mom_3m = metrics.get("momentum_3m")
        spy_1m = self.spy_metrics.get("momentum_1m")
        relative = mom_1m - spy_1m if mom_1m is not None and spy_1m is not None else None
        trend = trend_label(metrics)
        score = self._theme_score(metrics, relative)
        signal = self._signal(config["group"], mom_1m, mom_3m, relative, trend)
        companies = []
        theme_names = ROTATION_THEME_COMPANIES.get(ticker, config.get("names") or [])
        for name in theme_names[:15]:
            company_ticker = ROTATION_COMPANY_TICKERS.get(name)
            if not company_ticker:
                continue
            metrics = self.company_metrics.get(company_ticker, {})
            companies.append({
                "name": name,
                "ticker": company_ticker,
                "price": metrics.get("price"),
                "momentum_1m": metrics.get("momentum_1m"),
                "momentum_3m": metrics.get("momentum_3m"),
                "trend": trend_label(metrics),
                "volatility_20d": metrics.get("volatility_20d"),
                "score": self._company_score(metrics),
                "action": self._company_action(metrics),
            })

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
            price=metrics.get("price"),
            ma20=metrics.get("ma20"),
            ma50=metrics.get("ma50"),
            ma200=metrics.get("ma200"),
            volatility_20d=metrics.get("volatility_20d"),
            names=list(theme_names[:15]),
            news_topics=list(config.get("news_topics") or []),
            companies=companies,
        )

    @staticmethod
    def _company_score(metrics: Dict[str, Any]) -> int | None:
        if metrics.get("price") is None:
            return None
        score = 50
        trend = trend_label(metrics)
        if trend == "alcista":
            score += 20
        elif trend == "bajista":
            score -= 20
        for key, weight in (("momentum_1m", 15), ("momentum_3m", 15)):
            value = metrics.get(key)
            if value is not None:
                score += weight if value > 0 else -weight
        return max(0, min(100, score))

    @classmethod
    def _company_action(cls, metrics: Dict[str, Any]) -> str:
        score = cls._company_score(metrics)
        if score is None:
            return "SIN DATOS"
        if score >= 70:
            return "COMPRAR"
        if score <= 35:
            return "VENDER"
        return "ESPERAR"

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

        if group == "Tecnología":
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
            if t.group != "Tecnología" and t.relative_1m_vs_spy is not None and t.relative_1m_vs_spy > 1
        )
        leaders_resting = sum(
            1 for t in themes
            if t.group == "Tecnología" and t.momentum_1m is not None and t.momentum_1m < 0
        )
        asia_flow = sum(
            1 for t in themes
            if t.group == "Asia" and t.relative_1m_vs_spy is not None and t.relative_1m_vs_spy > 1
        )

        if receiver_flow >= 2 and leaders_resting >= 1:
            asia_note = " También hay flujo en Asia." if asia_flow else ""
            return (
                "ROTACIÓN ACTIVA Y SANA",
                "El dinero descansa parcialmente en IA/semis/tech y busca rezagados como biotech, salud, seguros o Asia."
                + asia_note,
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

    def _avg(self, values: List[float | None]) -> float | None:
        clean = [value for value in values if value is not None]
        if not clean:
            return None
        return sum(clean) / len(clean)
