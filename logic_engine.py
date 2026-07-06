"""
Módulo del Motor Lógico (logic_engine.py)

Procesa todas las variables macroeconómicas y emite diagnósticos.
Cada variable se evalúa de forma independiente.
"""

from enum import Enum
from typing import Dict, Any, List, Tuple

from risk_filters.calendar import check_macro_events
from risk_filters.sentiment import analyze_headlines
from config import (
    VIX_PANIC_THRESHOLD, VIX_ELEVATED_THRESHOLD, VIX_ACCELERATION_PCT,
    CORR_HIGH_THRESHOLD, CORR_LOW_THRESHOLD,
    US10Y_DANGER_THRESHOLD, US10Y_WARNING_THRESHOLD,
)

CORE_DATA_FIELDS = {
    "VIX": "VIX",
    "US10Y": "Bono 10Y",
    "Correlation_Proxy": "correlación sectorial",
}

SUPPORTING_DATA_FIELDS = {
    "PE_Forward": "PER forward",
    "M2_Change_Pct": "liquidez M2",
    "CPI_YoY_Pct": "IPC interanual",
}


class MarketStatus(Enum):
    """Constantes de estado del mercado."""
    BLOCKED = "BLOCKED"
    PANIC = "PANIC"
    CAUTION = "CAUTION"
    HEALTHY = "HEALTHY"
    UNKNOWN = "UNKNOWN"


STATUS_DISPLAY = {
    MarketStatus.BLOCKED: "🛑 SISTEMA EN PAUSA (BLOQUEADO POR RIESGO EXTREMO)",
    MarketStatus.PANIC:   "🚨 TECHO / PÁNICO INMINENTE (AUMENTAR LIQUIDEZ)",
    MarketStatus.CAUTION: "⚠️ MERCADO INESTABLE (PRECAUCIÓN)",
    MarketStatus.HEALTHY: "✅ TENDENCIA SANA / ROTACIÓN (COMPRAR/MANTENER)",
    MarketStatus.UNKNOWN: "❓ DATOS INSUFICIENTES PARA DIAGNOSTICAR",
}


class LogicEngine:
    def __init__(self, data: Dict[str, Any], headlines: List[str] | None = None):
        self.data = data
        self.headlines = headlines
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

        # ─── 8. Calendario Económico ───
        cal = check_macro_events()
        calendar_blocked = cal.get("should_block_signals", False)
        if cal["event_imminent"]:
            prefix = "🛑 CALENDARIO" if calendar_blocked else "ℹ️ CALENDARIO ESTIMADO"
            for ev in cal["events"]:
                self.alerts.append(f"{prefix}: {ev} (fuente: {cal.get('source', 'desconocida')}, confianza: {cal.get('confidence', 'UNKNOWN')}).")

        # ─── 9. Sentimiento de Noticias ───
        sentiment_blocked = False
        if self.headlines:
            sent = analyze_headlines(self.headlines)
            if sent["dominant_sentiment"] == "PANIC":
                self.alerts.append(f"🛑 SENTIMIENTO: {sent['details']}")
                sentiment_blocked = True
            elif sent["dominant_sentiment"] == "BULLISH":
                self.alerts.append(f"📈 SENTIMIENTO: {sent['details']}")
            else:
                self.alerts.append(f"ℹ️ SENTIMIENTO: {sent['details']}")
        else:
            self.alerts.append("ℹ️ SENTIMIENTO: Sin fuente de noticias conectada.")

        # ─── ÁRBOL DE DECISIÓN FINAL ───
        if calendar_blocked or sentiment_blocked:
            self.status = MarketStatus.BLOCKED
        elif is_panic or (is_vix_accelerating and is_corr_high):
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
