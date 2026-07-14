"""
Módulo del Motor Lógico (logic_engine.py)

Procesa todas las variables macroeconómicas y emite diagnósticos.
Cada variable se evalúa de forma independiente.
"""

from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Tuple

from risk_filters.calendar import check_macro_events
from risk_filters.sentiment import analyze_headlines, analyze_news_items
from user_settings import get_setting
from config import (
    VIX_PANIC_THRESHOLD, VIX_ELEVATED_THRESHOLD, VIX_ACCELERATION_PCT,
    CORR_HIGH_THRESHOLD, CORR_LOW_THRESHOLD,
    US10Y_DANGER_THRESHOLD, US10Y_WARNING_THRESHOLD,
    YIELD_CURVE_INVERSION_THRESHOLD, PE_PERCENTILE_HIGH, PE_PERCENTILE_LOW,
    CHINA_M2_EXPANSION_THRESHOLD, CHINA_M2_CONTRACTION_THRESHOLD,
)

CORE_DATA_FIELDS = {
    "VIX": "VIX",
    "US10Y": "Bono 10Y",
    "Correlation_Proxy": "correlación sectorial",
}

SUPPORTING_DATA_FIELDS = {
    "PE_Forward": "PER forward",
    "PE_Forward_Percentile": "percentil PER forward",
    "M2_Change_Pct": "liquidez M2",
    "CPI_YoY_Pct": "IPC interanual",
    "Yield_Curve_Spread": "curva de tipos 2Y-10Y",
    "China_M2_YoY_Pct": "liquidez China M2",
}


class MarketStatus(Enum):
    """Constantes de estado del mercado."""
    BLOCKED = "BLOCKED"
    PANIC = "PANIC"
    CAUTION = "CAUTION"
    HEALTHY = "HEALTHY"
    UNKNOWN = "UNKNOWN"


STATUS_DISPLAY = {
    MarketStatus.BLOCKED: "🛑 PAUSA OPERATIVA (filtro de riesgo activo)",
    MarketStatus.PANIC:   "🚨 TECHO / PÁNICO INMINENTE (AUMENTAR LIQUIDEZ)",
    MarketStatus.CAUTION: "⚠️ MERCADO INESTABLE (PRECAUCIÓN)",
    MarketStatus.HEALTHY: "✅ TENDENCIA SANA / ROTACIÓN (COMPRAR/MANTENER)",
    MarketStatus.UNKNOWN: "❓ DATOS INSUFICIENTES PARA DIAGNOSTICAR",
}


class LogicEngine:
    def __init__(
        self,
        data: Dict[str, Any],
        headlines: List[str] | None = None,
        news_items: List[Dict[str, Any]] | None = None,
    ):
        self.data = data
        self.headlines = headlines
        self.news_items = news_items
        self.status = MarketStatus.UNKNOWN
        self.alerts: List[str] = []

    def _add_data_quality_alerts(self) -> bool:
        """
        Informa huecos de datos y devuelve True si hay datos mínimos para
        emitir un diagnóstico sano, no solo ausencia de alertas.
        """
        missing_core = [label for key, label in CORE_DATA_FIELDS.items() if self.data.get(key) is None]
        missing_support = [label for key, label in SUPPORTING_DATA_FIELDS.items() if self.data.get(key) is None]

        if missing_core:
            self.alerts.append(
                "ℹ️ DATOS CRÍTICOS INCOMPLETOS: falta "
                + ", ".join(missing_core)
                + ". No se confirmará estado saludable con esta muestra."
            )
        if missing_support:
            self.alerts.append(
                "ℹ️ DATOS DE APOYO NO DISPONIBLES: falta "
                + ", ".join(missing_support)
                + "."
            )

        available_core = len(CORE_DATA_FIELDS) - len(missing_core)
        return available_core >= 2 and self.data.get("VIX") is not None

    def evaluate(self) -> Tuple[MarketStatus, List[str]]:
        """Evalúa el estado del mercado. Retorna (MarketStatus, alertas)."""
        d = self.data
        self.alerts.clear()

        is_vix_accelerating = False
        is_panic = False
        has_minimum_data = self._add_data_quality_alerts()

        # ─── 1. VIX: Nivel absoluto ───
        vix = d.get("VIX")
        if vix is not None:
            if vix > VIX_PANIC_THRESHOLD:
                self.alerts.append(f"🚨 PÁNICO EXTREMO: VIX = {vix:.1f} (umbral: {VIX_PANIC_THRESHOLD}).")
                is_panic = True
            elif vix > VIX_ELEVATED_THRESHOLD:
                self.alerts.append(f"⚠️ VIX ELEVADO: {vix:.1f} (umbral: {VIX_ELEVATED_THRESHOLD}).")

        # ─── 2. VIX: Aceleración por temporalidades ───
        for label, key in [("5D", "VIX_MA5"), ("10D", "VIX_MA10"), ("20D", "VIX_MA20")]:
            ma = d.get(key)
            if vix is not None and ma is not None:
                if vix > ma * (1 + VIX_ACCELERATION_PCT):
                    pct = ((vix - ma) / ma) * 100
                    self.alerts.append(f"⚠️ ACELERACIÓN VIX vs MA({label}): +{pct:.1f}%.")
                    is_vix_accelerating = True

        # Tendencia alcista sostenida
        mas = [d.get(k) for k in ("VIX_MA5", "VIX_MA10", "VIX_MA20") if d.get(k) is not None]
        if vix is not None and mas and all(vix > m for m in mas):
            self.alerts.append("⚠️ TENDENCIA VIX ALCISTA: Por encima de todas las MAs disponibles.")

        # ─── 3. Correlación Sectorial ───
        is_corr_high = False
        corr = d.get("Correlation_Proxy")
        if corr is not None:
            ac = abs(corr)
            if ac > CORR_HIGH_THRESHOLD:
                kind = "caída conjunta" if corr > 0 else "flight-to-safety"
                self.alerts.append(f"🚨 CORRELACIÓN ALTA ({kind}): {corr:.3f}.")
                is_corr_high = True
            elif ac < CORR_LOW_THRESHOLD:
                self.alerts.append(f"✅ CORRELACIÓN BAJA: {corr:.3f}. Rotación sana.")

        # ─── 4. Tipos de Interés ───
        us10y = d.get("US10Y")
        if us10y is not None:
            if us10y > US10Y_DANGER_THRESHOLD:
                self.alerts.append(f"🚨 RIESGO ESTRUCTURAL: Bono 10Y = {us10y:.2f}%.")
            elif us10y > US10Y_WARNING_THRESHOLD:
                self.alerts.append(f"⚠️ TIPOS ALTOS: Bono 10Y = {us10y:.2f}%.")

        # ─── 5. PER (Múltiplos de Valoración) ───
        pe_fwd = d.get("PE_Forward")
        pe_trail = d.get("PE_Trailing")
        if pe_fwd is not None:
            if pe_fwd > 25:
                self.alerts.append(f"⚠️ PER FORWARD ELEVADO: {pe_fwd:.1f}x. Expectativas altas.")
            elif pe_fwd < 18:
                self.alerts.append(f"✅ PER FORWARD ATRACTIVO: {pe_fwd:.1f}x.")
        if pe_trail is not None and pe_trail > 28:
            self.alerts.append(f"⚠️ PER TRAILING ALTO: {pe_trail:.1f}x.")

        pe_pct = d.get("PE_Forward_Percentile")
        if pe_pct is not None:
            if pe_pct >= PE_PERCENTILE_HIGH:
                self.alerts.append(f"⚠️ PER FORWARD CARO vs HISTÓRICO: percentil {pe_pct:.0f}.")
            elif pe_pct <= PE_PERCENTILE_LOW:
                self.alerts.append(f"✅ PER FORWARD BARATO vs HISTÓRICO: percentil {pe_pct:.0f}.")

        # ─── 5b. Curva de tipos (2Y-10Y) ───
        spread = d.get("Yield_Curve_Spread")
        if spread is not None:
            if spread <= YIELD_CURVE_INVERSION_THRESHOLD:
                self.alerts.append(f"🚨 CURVA INVERTIDA: spread 2Y-10Y = {spread:+.2f} pp.")
            elif spread < 0.5:
                self.alerts.append(f"⚠️ CURVA PLANA: spread 2Y-10Y = {spread:+.2f} pp.")

        # ─── 6. Liquidez Global (M2) ───
        m2_chg = d.get("M2_Change_Pct")
        if m2_chg is not None:
            if m2_chg < -1.0:
                self.alerts.append(f"🚨 CONTRACCIÓN M2: {m2_chg:+.2f}% en 14 semanas. Liquidez cayendo.")
            elif m2_chg > 1.0:
                self.alerts.append(f"✅ EXPANSIÓN M2: {m2_chg:+.2f}% en 14 semanas. Liquidez creciente.")
            else:
                self.alerts.append(f"ℹ️ M2 ESTABLE: {m2_chg:+.2f}% en 14 semanas.")

        # ─── 7. Inflación (IPC) ───
        cpi_yoy = d.get("CPI_YoY_Pct")
        if cpi_yoy is not None:
            if cpi_yoy > 4.0:
                self.alerts.append(f"🚨 INFLACIÓN ALTA: IPC interanual = {cpi_yoy:.1f}%.")
            elif cpi_yoy > 3.0:
                self.alerts.append(f"⚠️ INFLACIÓN PEGAJOSA: IPC interanual = {cpi_yoy:.1f}%.")
            elif cpi_yoy < 2.0:
                self.alerts.append(f"✅ INFLACIÓN CONTROLADA: IPC interanual = {cpi_yoy:.1f}%.")

        # ─── 7b. Liquidez China ───
        china_m2 = d.get("China_M2_YoY_Pct")
        if china_m2 is not None:
            if china_m2 >= CHINA_M2_EXPANSION_THRESHOLD:
                self.alerts.append(f"✅ LIQUIDEZ CHINA EXPANSIVA: M2 YoY = {china_m2:.1f}%.")
            elif china_m2 <= CHINA_M2_CONTRACTION_THRESHOLD:
                self.alerts.append(f"⚠️ LIQUIDEZ CHINA DÉBIL: M2 YoY = {china_m2:.1f}%.")

        # ─── 7c. Mercados globales ───
        global_markets = d.get("GlobalMarkets", {})
        global_lines = []
        for region, metrics in global_markets.items():
            mom = metrics.get("momentum_1m")
            if mom is not None:
                global_lines.append(f"{region} {mom:+.1f}%")
        if global_lines:
            self.alerts.append("🌍 MERCADOS GLOBALES 1M: " + " | ".join(global_lines[:4]) + ".")

        # ─── 8. Calendario Económico ───
        as_of = None
        raw_as_of = d.get("_as_of")
        if raw_as_of is not None:
            try:
                as_of = datetime.fromisoformat(str(raw_as_of).replace("Z", "+00:00"))
            except ValueError:
                as_of = None
        cal = check_macro_events(as_of=as_of, block_hours=get_setting("calendar_block_hours"))
        calendar_blocked = cal.get("should_block_signals", False)
        if cal["event_imminent"]:
            prefix = "🛑 CALENDARIO" if calendar_blocked else "ℹ️ CALENDARIO ESTIMADO"
            block_note = f"bloqueo {cal.get('block_hours', get_setting('calendar_block_hours'))}h"
            for ev in cal["events"]:
                self.alerts.append(
                    f"{prefix}: {ev} (fuente: {cal.get('source', 'desconocida')}, "
                    f"confianza: {cal.get('confidence', 'UNKNOWN')}, {block_note})."
                )
            for ev in cal.get("warning_events", []):
                self.alerts.append(
                    f"⚠️ CALENDARIO PRÓXIMO: {ev.get('title')} en {ev.get('hours_until')}h "
                    f"(ventana estricta {get_setting('calendar_block_hours')}h activa)."
                )

        # ─── 9. Sentimiento de Noticias ───
        sentiment_blocked = False
        if self.news_items:
            sent = analyze_news_items(self.news_items)
        elif self.headlines:
            sent = analyze_headlines(self.headlines)
        else:
            sent = None

        # Guardar resultado estructurado para que DecisionEngine lo use directamente
        self.sentiment_result = sent

        if sent:
            sentiment_label = sent["dominant_sentiment"]
            if sentiment_label == "PANIC":
                self.alerts.append(
                    f"🛑 SENTIMIENTO: Miedo dominante en noticias → reducir exposición. "
                    f"(pánico {sent['panic_hits']}, alcista {sent['bull_hits']}, "
                    f"{sent.get('headline_count', len(self.news_items or []))} titulares)"
                )
                sentiment_blocked = get_setting("sentiment_blocks_signals")
            elif sentiment_label == "BULLISH":
                self.alerts.append(
                    f"📈 SENTIMIENTO: Optimismo dominante → contexto favorable para riesgo. "
                    f"(alcista {sent['bull_hits']}, pánico {sent['panic_hits']})"
                )
            elif sentiment_label == "MIXED":
                self.alerts.append(
                    f"⚠️ SENTIMIENTO: Señales mixtas → prudencia, esperar claridad. "
                    f"(pánico {sent['panic_hits']}, alcista {sent['bull_hits']})"
                )
            else:
                self.alerts.append("ℹ️ SENTIMIENTO: Sin señales claras en titulares.")
        else:
            self.sentiment_result = None
            self.alerts.append("ℹ️ SENTIMIENTO: Sin fuente de noticias conectada.")

        # ─── ÁRBOL DE DECISIÓN FINAL ───
        yield_inverted = spread is not None and spread <= YIELD_CURVE_INVERSION_THRESHOLD
        if calendar_blocked or sentiment_blocked:
            self.status = MarketStatus.BLOCKED
        elif is_panic or yield_inverted or (is_vix_accelerating and is_corr_high):
            self.status = MarketStatus.PANIC
        elif is_vix_accelerating or is_corr_high:
            self.status = MarketStatus.CAUTION
        elif has_minimum_data:
            self.status = MarketStatus.HEALTHY
        else:
            self.status = MarketStatus.UNKNOWN

        return self.status, self.alerts


if __name__ == "__main__":
    print("─── Test: Mercado en estrés ───")
    stress = {
        "VIX": 32.0, "VIX_MA5": 22.0, "VIX_MA10": 18.5, "VIX_MA20": 16.0,
        "US10Y": 5.2, "Correlation_Proxy": 0.75,
        "PE_Forward": 27.0, "PE_Trailing": 30.0,
        "M2_Change_Pct": -2.5, "CPI_YoY_Pct": 4.5,
    }
    e = LogicEngine(stress)
    s, a = e.evaluate()
    print(f"  STATUS: {STATUS_DISPLAY[s]}")
    for x in a:
        print(f"  {x}")
