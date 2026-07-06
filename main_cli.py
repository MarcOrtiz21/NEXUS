"""
Interfaz de Línea de Comandos (main_cli.py)

Panel interactivo con diagnósticos macroeconómicos.
Soporta ejecución única y modo loop con refresco periódico.
"""

import sys
import time
import argparse
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from config import REFRESH_INTERVAL_SECONDS, FRED_API_KEY
from data_ingestion import fetch_market_data
from logic_engine import LogicEngine, MarketStatus, STATUS_DISPLAY
from risk_filters.news_feed import fetch_headlines

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

console = Console()

STATUS_COLORS = {
    MarketStatus.BLOCKED: "bold white on red",
    MarketStatus.PANIC:   "bold white on red",
    MarketStatus.CAUTION: "bold black on yellow",
    MarketStatus.HEALTHY: "bold white on green",
    MarketStatus.UNKNOWN: "bold white on blue",
}


def _fmt(val, decimals: int = 2, suffix: str = "") -> str:
    if val is None:
        return "[dim]—[/dim]"
    return f"{val:.{decimals}f}{suffix}"


def _color(val, red_above=None, yellow_above=None, green_below=None, invert=False):
    """Devuelve un color rich basado en umbrales."""
    if val is None:
        return "dim"
    if red_above is not None and val > red_above:
        return "red" if not invert else "green"
    if yellow_above is not None and val > yellow_above:
        return "yellow"
    if green_below is not None and val < green_below:
        return "green" if not invert else "red"
    return "white"


def generate_dashboard(use_news: bool = True):
    """Genera y muestra el dashboard completo."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with console.status("[bold green]Ingiriendo datos (NEXUS)...", spinner="dots"):
        data = fetch_market_data()
        headlines = fetch_headlines() if use_news else None
        engine = LogicEngine(data, headlines=headlines if headlines else None)
        status, alerts = engine.evaluate()

    console.clear()

    # ─── Cabecera ───
    console.print(Panel(
        f"[bold cyan]NEXUS: Networked Economic cross-asset Utility System[/bold cyan]\n"
        f"[italic]Terminal de Análisis Macroeconómico v2.0 — {now}[/italic]",
        box=box.DOUBLE, expand=False,
    ))
    console.print("")

    # ─── Tabla 1: Mercado ───
    t1 = Table(title="Mercado", box=box.SIMPLE_HEAVY, header_style="bold magenta")
    t1.add_column("Métrica", style="cyan", no_wrap=True)
    t1.add_column("Actual", justify="right")
    t1.add_column("MA 5D", justify="right")
    t1.add_column("MA 10D", justify="right")
    t1.add_column("MA 20D", justify="right")

    vix = data.get("VIX")
    vc = _color(vix, red_above=25, yellow_above=16)
    t1.add_row("VIX", f"[{vc}]{_fmt(vix)}[/{vc}]",
               _fmt(data.get("VIX_MA5")), _fmt(data.get("VIX_MA10")), _fmt(data.get("VIX_MA20")))

    us10y = data.get("US10Y")
    uc = _color(us10y, red_above=5.0, yellow_above=4.5)
    t1.add_row("Bono 10Y", f"[{uc}]{_fmt(us10y, suffix='%')}[/{uc}]", "—", "—", "—")

    corr = data.get("Correlation_Proxy")
    abs_c = abs(corr) if corr is not None else None
    cc = _color(abs_c, red_above=0.6, yellow_above=0.3)
    t1.add_row("Corr. Sectorial", f"[{cc}]{_fmt(corr, 3)}[/{cc}]", "—", "—", "—")

    console.print(t1)
    console.print("")

    # ─── Tabla 2: Valoración y Macro ───
    t2 = Table(title="Valoración y Macro", box=box.SIMPLE_HEAVY, header_style="bold magenta")
    t2.add_column("Métrica", style="cyan", no_wrap=True)
    t2.add_column("Valor", justify="right")
    t2.add_column("Estado", justify="left")

    # PER
    pe_f = data.get("PE_Forward")
    pe_t = data.get("PE_Trailing")
    pc = _color(pe_f, red_above=25, yellow_above=20)
    pe_status = "Caro" if pe_f and pe_f > 25 else ("Neutro" if pe_f and pe_f > 18 else "Atractivo" if pe_f else "—")
    t2.add_row("PER Forward (SPY)", f"[{pc}]{_fmt(pe_f, 1)}x[/{pc}]", pe_status)
    t2.add_row("PER Trailing (SPY)", _fmt(pe_t, 1, "x"), "—")

    # M2
    m2_chg = data.get("M2_Change_Pct")
    if m2_chg is not None:
        mc = "green" if m2_chg > 0 else "red"
        m2_status = "Expansión" if m2_chg > 0 else "Contracción"
        t2.add_row("Liquidez M2 (14 sem.)", f"[{mc}]{m2_chg:+.2f}%[/{mc}]", m2_status)
    else:
        t2.add_row("Liquidez M2", "[dim]—[/dim]", "[dim]Requiere FRED_API_KEY[/dim]")

    # IPC
    cpi_yoy = data.get("CPI_YoY_Pct")
    if cpi_yoy is not None:
        ic = _color(cpi_yoy, red_above=4.0, yellow_above=3.0)
        cpi_st = "Alta" if cpi_yoy > 4 else ("Pegajosa" if cpi_yoy > 3 else "Controlada")
        t2.add_row("Inflación IPC (YoY)", f"[{ic}]{cpi_yoy:.1f}%[/{ic}]", cpi_st)
    else:
        t2.add_row("Inflación IPC", "[dim]—[/dim]", "[dim]Requiere FRED_API_KEY[/dim]")

    console.print(t2)
    console.print("")

    # ─── Alertas ───
    if alerts:
        console.print(Panel("\n".join(alerts), title="Alertas del Motor Lógico", border_style="yellow"))
    else:
        console.print(Panel("[green]Sin anomalías.[/green]", title="Alertas", border_style="green"))
    console.print("")

    # ─── Diagnóstico ───
    display = STATUS_DISPLAY.get(status, str(status))
    color = STATUS_COLORS.get(status, "bold white on blue")
    console.print(f"[{color}] DIAGNÓSTICO: {display} [/{color}]")

    # ─── Info de noticias ───
    if headlines:
        console.print(f"\n[dim]Sentimiento calculado sobre {len(headlines)} titulares reales (RSS).[/dim]")
    if not FRED_API_KEY:
        console.print("[dim]M2 e IPC desactivados. Configura FRED_API_KEY para activarlos.[/dim]")
    console.print("")


def main():
    parser = argparse.ArgumentParser(description="NEXUS — Terminal de Análisis Macroeconómico")
    parser.add_argument("--loop", action="store_true", help="Modo loop: refresca periódicamente.")
    parser.add_argument("--interval", type=int, default=REFRESH_INTERVAL_SECONDS,
                        help=f"Segundos entre refrescos (defecto: {REFRESH_INTERVAL_SECONDS}).")
    parser.add_argument("--no-news", action="store_true", help="Desactiva la descarga de noticias RSS.")
    args = parser.parse_args()

    if args.loop:
        console.print(f"[bold cyan]Modo loop activado. Refresco cada {args.interval} segundos.[/bold cyan]")
        console.print("[dim]Presiona Ctrl+C para salir.[/dim]\n")
        while True:
            generate_dashboard(use_news=not args.no_news)
            console.print(f"[dim]Próximo refresco en {args.interval}s. Ctrl+C para salir.[/dim]")
            time.sleep(args.interval)
    else:
        generate_dashboard(use_news=not args.no_news)
        console.print("[dim]Usa --loop para refresco periódico. Ctrl+C para salir.[/dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Saliendo de NEXUS...[/bold red]")
