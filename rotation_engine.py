"""
Motor de rotación sectorial/temática de NEXUS.

Traduce proxies ETF en una lectura legible: qué liderazgos descansan y
qué sectores rezagados están recibiendo flujo.
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Set

from config import (
    MOMENTUM_1M_SCALE,
    MOMENTUM_3M_SCALE,
    RELATIVE_1M_SCALE,
    ROTATION_FLOW_MOM1,
    ROTATION_FLOW_RELATIVE,
    ROTATION_LEADER_COUNT_MAX,
    ROTATION_LEADER_COUNT_MIN,
)
from utils import trend_label, weighted_signed
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
    {
        "ticker": "EWP", "group": "Europa", "theme": "España / IBEX",
        "represents": "proxy del mercado español (IBEX vía EWP)",
        "names": ["Santander", "BBVA", "Iberdrola", "Inditex", "Telefónica"],
        "news_topics": ["Fed/tipos", "Geopolítica", "Resultados"],
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
    leadership: str = ""


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
        leaders = self._observed_leaders(themes)
        leader_ids = {theme.ticker for theme in leaders}
        for theme in themes:
            is_leader = theme.ticker in leader_ids
            theme.signal = self._signal(
                mom_1m=theme.momentum_1m,
                mom_3m=theme.momentum_3m,
                relative=theme.relative_1m_vs_spy,
                trend=theme.trend,
                is_leader=is_leader,
            )
            if is_leader:
                theme.leadership = "lider"
            elif self._is_flow_receiver(theme, leader_ids):
                theme.leadership = "receptor"
            else:
                theme.leadership = "otros"

        leaders_avg = self._avg([t.momentum_1m for t in themes if t.ticker in leader_ids])
        receivers_avg = self._avg([t.momentum_1m for t in themes if t.ticker not in leader_ids])
        state, summary = self._state_and_summary(themes, leader_ids, leaders_avg, receivers_avg)

        return RotationResult(
            state=state,
            summary=summary,
            leaders_avg_1m=leaders_avg,
            receivers_avg_1m=receivers_avg,
            themes=themes,
        )

    def _evaluate_theme(self, config: Dict[str, Any]) -> RotationTheme:
        ticker = config["ticker"]
        etf = self.rotation_assets.get(ticker, {})
        mom_1m = etf.get("momentum_1m")
        mom_3m = etf.get("momentum_3m")
        spy_1m = self.spy_metrics.get("momentum_1m")
        relative = mom_1m - spy_1m if mom_1m is not None and spy_1m is not None else None
        trend = trend_label(etf)
        score = self._theme_score(etf, relative)
        companies = []
        theme_names = ROTATION_THEME_COMPANIES.get(ticker, config.get("names") or [])
        for name in theme_names[:15]:
            company_ticker = ROTATION_COMPANY_TICKERS.get(name)
            if not company_ticker:
                continue
            company = self.company_metrics.get(company_ticker, {})
            companies.append({
                "name": name,
                "ticker": company_ticker,
                "price": company.get("price"),
                "momentum_1m": company.get("momentum_1m"),
                "momentum_3m": company.get("momentum_3m"),
                "trend": trend_label(company),
                "volatility_20d": company.get("volatility_20d"),
                "score": self._company_score(company),
                "action": self._company_action(company),
            })

        return RotationTheme(
            ticker=ticker,
            group=config["group"],
            theme=config["theme"],
            represents=config["represents"],
            signal="",
            score=score,
            momentum_1m=mom_1m,
            momentum_3m=mom_3m,
            relative_1m_vs_spy=relative,
            trend=trend,
            price=etf.get("price"),
            ma20=etf.get("ma20"),
            ma50=etf.get("ma50"),
            ma200=etf.get("ma200"),
            volatility_20d=etf.get("volatility_20d"),
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
        for key, weight, scale in (
            ("momentum_1m", 15, MOMENTUM_1M_SCALE),
            ("momentum_3m", 15, MOMENTUM_3M_SCALE),
        ):
            value = metrics.get(key)
            if value is not None:
                score += weighted_signed(value, weight, scale)
        return max(0, min(100, score))

    @classmethod
    def _company_action(cls, metrics: Dict[str, Any]) -> str:
        score = cls._company_score(metrics)
        if score is None:
            return "SIN DATOS"
        if score >= 70:
            return "FUERTE"
        if score <= 35:
            return "DEBIL"
        return "OBSERVAR"

    def _theme_score(self, metrics: Dict[str, Any], relative: float | None) -> int:
        price = metrics.get("price")
        if price is None:
            return 0

        score = 50
        for ma_key, weight in (("ma20", 8), ("ma50", 10), ("ma200", 8)):
            ma = metrics.get(ma_key)
            if ma is not None:
                score += weight if price > ma else -weight

        for mom_key, weight, scale in (
            ("momentum_1m", 10, MOMENTUM_1M_SCALE),
            ("momentum_3m", 8, MOMENTUM_3M_SCALE),
        ):
            momentum = metrics.get(mom_key)
            if momentum is not None:
                score += weighted_signed(momentum, weight, scale)

        if relative is not None:
            score += weighted_signed(relative, 8, RELATIVE_1M_SCALE)

        return max(0, min(100, score))

    def _signal(
        self,
        mom_1m: float | None,
        mom_3m: float | None,
        relative: float | None,
        trend: str,
        is_leader: bool,
    ) -> str:
        if mom_1m is None:
            return "Sin datos"

        outperforming = relative is not None and relative > ROTATION_FLOW_RELATIVE
        underperforming = relative is not None and relative < -ROTATION_FLOW_RELATIVE

        if is_leader:
            if mom_1m < 0 and mom_3m is not None and mom_3m > 0:
                return "Descanso sano tras liderazgo"
            if mom_1m < 0 and underperforming:
                return "Corrección activa"
            if trend == "alcista" and mom_1m > 0:
                return "Liderazgo aún fuerte"
            return "Base en formación"

        if mom_1m > ROTATION_FLOW_MOM1 and outperforming:
            return "Entrada clara de flujo"
        if mom_1m > 0:
            return "Mejora incipiente"
        if trend == "alcista":
            return "Mantiene estructura"
        return "Aún sin confirmación"

    def _observed_leaders(self, themes: List[RotationTheme]) -> List[RotationTheme]:
        spy_3m = self.spy_metrics.get("momentum_3m")
        spy_1m = self.spy_metrics.get("momentum_1m")

        def rank_key(theme: RotationTheme) -> float:
            if theme.momentum_3m is not None:
                return float(theme.momentum_3m)
            return float(theme.momentum_1m or 0)

        def beats_spy(theme: RotationTheme) -> bool:
            if theme.momentum_3m is not None and spy_3m is not None:
                return theme.momentum_3m > spy_3m
            if theme.momentum_1m is not None and spy_1m is not None:
                return theme.momentum_1m > spy_1m
            return False

        eligible = [theme for theme in themes if theme.momentum_3m is not None or theme.momentum_1m is not None]
        ranked = sorted(eligible, key=rank_key, reverse=True)
        beating = [theme for theme in ranked if beats_spy(theme)]
        if len(beating) >= ROTATION_LEADER_COUNT_MIN:
            return beating[:ROTATION_LEADER_COUNT_MAX]
        return ranked[: min(ROTATION_LEADER_COUNT_MIN, len(ranked))]

    def _state_and_summary(
        self,
        themes: List[RotationTheme],
        leader_ids: Set[str],
        leaders_avg: float | None,
        receivers_avg: float | None,
    ) -> tuple[str, str]:
        if leaders_avg is None or receivers_avg is None:
            return "SIN DATOS", "No hay datos suficientes para evaluar la rotación."

        resting = self._resting_leaders(themes, leader_ids)
        receiving = self._flow_receivers(themes, leader_ids)
        leaving_txt = self._theme_names(resting)
        entering_txt = self._theme_names(receiving)

        if len(receiving) >= 2 and resting:
            return (
                "ROTACIÓN ACTIVA Y SANA",
                f"El liderazgo descansa en {leaving_txt}. El flujo relativo más claro está en {entering_txt}.",
            )
        if len(receiving) >= 2:
            return (
                "ROTACIÓN HACIA REZAGADOS",
                f"El flujo relativo más claro está en {entering_txt}, aunque los líderes aún no han corregido con claridad.",
            )
        if len(resting) >= 2 and receivers_avg <= 0:
            return (
                "DESCANSO SIN RELEVO CLARO",
                f"Corrigen {leaving_txt}, pero todavía no aparece un receptor con ventaja clara frente a SPY.",
            )
        if leaders_avg > receivers_avg:
            strongest = self._theme_names(
                sorted(
                    [t for t in themes if t.ticker in leader_ids and t.momentum_1m is not None],
                    key=lambda t: t.momentum_1m or 0,
                    reverse=True,
                ),
                limit=2,
            )
            lead = f" Mandan {strongest}." if strongest else ""
            return (
                "LIDERAZGO AÚN DOMINANTE",
                "Los líderes observados siguen al frente; la rotación hacia rezagados no está confirmada."
                + lead,
            )
        return (
            "ROTACIÓN EN DESARROLLO",
            "Hay señales mixtas: conviene vigilar si algún receptor sostiene ventaja frente a SPY.",
        )

    @staticmethod
    def _resting_leaders(themes: List[RotationTheme], leader_ids: Set[str]) -> List[RotationTheme]:
        resting = [
            theme for theme in themes
            if theme.ticker in leader_ids and theme.momentum_1m is not None and theme.momentum_1m < 0
        ]
        return sorted(resting, key=lambda theme: theme.momentum_1m or 0)

    @staticmethod
    def _is_flow_receiver(theme: RotationTheme, leader_ids: Set[str]) -> bool:
        if theme.ticker in leader_ids:
            return False
        if theme.momentum_1m is None or theme.relative_1m_vs_spy is None:
            return False
        return (
            theme.relative_1m_vs_spy > ROTATION_FLOW_RELATIVE
            and theme.momentum_1m > ROTATION_FLOW_MOM1
        )

    @classmethod
    def _flow_receivers(cls, themes: List[RotationTheme], leader_ids: Set[str]) -> List[RotationTheme]:
        receiving = [theme for theme in themes if cls._is_flow_receiver(theme, leader_ids)]
        return sorted(receiving, key=lambda theme: theme.relative_1m_vs_spy or 0, reverse=True)

    @staticmethod
    def _theme_names(themes: List[RotationTheme], limit: int = 3) -> str:
        names = [theme.theme for theme in themes[:limit] if theme.theme]
        if not names:
            return ""
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} y {names[1]}"
        return f"{', '.join(names[:-1])} y {names[-1]}"

    def _avg(self, values: List[float | None]) -> float | None:
        clean = [value for value in values if value is not None]
        if not clean:
            return None
        return sum(clean) / len(clean)
