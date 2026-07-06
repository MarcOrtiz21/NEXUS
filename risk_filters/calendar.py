"""
Filtro de Calendario Económico (calendar.py)

Detecta eventos macroeconómicos inminentes de alto impacto
(reuniones del FOMC y datos de IPC)
que invalidan las señales técnicas del motor lógico.

NOTA: Las fechas están hardcodeadas como estimaciones. Para producción,
conectar a una API de calendario económico (ej. Trading Economics, Investing.com).
Actualizar manualmente este archivo cuando la FED publique su calendario oficial.
"""

from datetime import datetime, timedelta
from typing import Dict

CALENDAR_SOURCE = "estimado_manual"
CALENDAR_CONFIDENCE = "LOW"
CALENDAR_BLOCKS_SIGNALS = False


# ─── Fechas de eventos de alto impacto (2026, estimadas) ───
# Fuente: Basado en el patrón histórico del FOMC (~8 reuniones/año).
# ⚠️ ESTAS FECHAS SON ESTIMACIONES. Verificar con https://www.federalreserve.gov/
FOMC_DATES = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

# Datos de IPC de EE.UU. se publican mensualmente (generalmente el 2º martes del mes).
# ⚠️ ESTAS FECHAS SON ESTIMACIONES.
CPI_DATES = [
    "2026-01-13", "2026-02-11", "2026-03-10", "2026-04-14",
    "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-15", "2026-10-13", "2026-11-10", "2026-12-10",
]


def check_macro_events(lookahead_days: int = 1) -> Dict:
    """
    Comprueba si hay eventos macroeconómicos inminentes.

    Args:
        lookahead_days: Número de días hacia adelante a comprobar (defecto: 1 = hoy y mañana).

    Returns:
        Diccionario con:
        - event_imminent (bool): True si hay evento estimado en el horizonte.
        - should_block_signals (bool): True solo con calendario oficial/verificado.
        - events (list): Lista de eventos detectados con sus detalles.
        - source/confidence: trazabilidad de la fuente usada.
    """
    today = datetime.now().date()
    horizon = [today + timedelta(days=d) for d in range(lookahead_days + 1)]

    events_found = []

    # Comprobar FOMC
    for date_str in FOMC_DATES:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date in horizon:
            when = "HOY" if event_date == today else f"en {(event_date - today).days} día(s)"
            events_found.append(f"Reunión del FOMC (FED) {when} ({date_str})")

    # Comprobar IPC
    for date_str in CPI_DATES:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date in horizon:
            when = "HOY" if event_date == today else f"en {(event_date - today).days} día(s)"
            events_found.append(f"Publicación del IPC (Inflación) {when} ({date_str})")

    return {
        "event_imminent": len(events_found) > 0,
        "should_block_signals": CALENDAR_BLOCKS_SIGNALS and len(events_found) > 0,
        "events": events_found,
        "source": CALENDAR_SOURCE,
        "confidence": CALENDAR_CONFIDENCE,
    }


if __name__ == "__main__":
    res = check_macro_events()
    print("Estado del calendario económico:")
    if res["event_imminent"]:
        for ev in res["events"]:
            print(f"  ⚠️ {ev}")
    else:
        print("  ✅ No hay eventos macro inminentes.")
