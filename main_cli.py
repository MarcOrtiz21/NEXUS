"""
Interfaz de Línea de Comandos (main_cli.py)

Dashboard macroeconómico en terminal con foco en claridad visual y trazabilidad.
"""

import sys
import time
import argparse
from datetime import datetime

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

from config import REFRESH_INTERVAL_SECONDS, FRED_API_KEY
from data_ingestion import fetch_market_data
from decision_engine import DecisionEngine
from history import export_decision_snapshot
from logic_engine import LogicEngine, MarketStatus, STATUS_DISPLAY
from risk_filters.news_feed import fetch_news_items

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

console = Console()

STATUS_COLORS = {
    MarketStatus.BLOCKED: "bold white on red",
    MarketStatus.PANIC: "bold white on red",
    MarketStatus.CAUTION: "bold black on yellow",
    MarketStatus.HEALTHY: "bold white on green",
    MarketStatus.UNKNOWN: "bold white on blue",
}


def _fmt(val, decimals: int = 2, suffix: str = "") -> str:
    if val is None:
        return "[dim]—[/dim]"
    return f"{val:.{decimals}f}{suffix}"


def _score_style(score: int) -> str:
    if score >= 75:
        return "green"
    if score >= 60:
        return "bright_green"
    if score >= 45:
        return "yellow"
    if score >= 30:
        return "bright_yellow"
    return "red"


def _score_bar(score: int, width: int = 24) -> str:
    score = max(0, min(100, score))
    filled = round((score / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    style = _score_style(score)
    return f"[{style}]{bar}[/{style}] {score:>3}/100"


def _color(val, red_above=None, yellow_above=None, green_below=None, invert=False):
    if val is None:
        return "dim"
    if red_above is not None and val > red_above:
        return "red" if not invert else "green"
    if yellow_above is not None and val > yellow_above:
        return "yellow"
    if green_below is not None and val < green_below:
        return "green" if not invert else "red"
    return "white"


def _decision_color(action: str) -> str:
    if action in ("COMPRAR", "COMPRAR PARCIAL"):
        return "bold white on green"
    if action in ("MANTENER", "ESPERAR"):
        return "bold black on yellow"
    if action == "DATOS INSUFICIENTES":
        return "bold white on blue"
    return "bold white on red"


def _trend_symbol(trend: str) -> str:
    if trend == "alcista":
        return "↑"
    if trend == "bajista":
        return "↓"
    if trend == "mixta":
        return "↔"
    return "·"


def _render_header(now: str, status: MarketStatus, compact: bool):
    badge = STATUS_DISPLAY.get(status, str(status))
    status_color = STATUS_COLORS.get(status, "bold white on blue")
    title = (
        "[bold cyan]NEXUS[/bold cyan]  [dim]- Networked Economic cross-asset Utility System[/dim]\n"
        f"[italic]Terminal de Análisis Macroeconómico[/italic]  [dim]{now}[/dim]\n"
        f"[{status_color}] {badge} [/{status_color}]"
    )
    console.print(Panel(title, box=box.DOUBLE, border_style="cyan", expand=not compact))
    console.print("")


def _render_data_quality(data):
    quality = data.get("DataQuality", {})
    if not quality:
        return
    status_counts = {}
    for item in quality.values():
        status = item.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    snapshot = quality.get("snapshot", {})
    captured = snapshot.get("captured_at", "—")
    summary = " | ".join(
        f"{status}: {count}"
        for status, count in sorted(status_counts.items(), key=lambda x: x[0])
    )
    console.print(
        Panel(
            f"[bold]Calidad/Frescura:[/bold] {summary}\n[dim]Snapshot UTC: {captured}[/dim]",
            title="Trazabilidad de Datos",
            border_style="blue",
        )
    )
    console.print("")


def _build_market_table(data):
    table = Table(title="Mercado", box=box.SIMPLE_HEAVY, header_style="bold magenta")
    table.add_column("Métrica", style="cyan", no_wrap=True)
    table.add_column("Actual", justify="right")
    table.add_column("MA 5D", justify="right")
    table.add_column("MA 10D", justify="right")
    table.add_column("MA 20D", justify="right")

    vix = data.get("VIX")
    vc = _color(vix, red_above=25, yellow_above=16)
    table.add_row(
        "VIX",
        f"[{vc}]{_fmt(vix)}[/{vc}]",
        _fmt(data.get("VIX_MA5")),
        _fmt(data.get("VIX_MA10")),
        _fmt(data.get("VIX_MA20")),
    )

    us10y = data.get("US10Y")
    uc = _color(us10y, red_above=5.0, yellow_above=4.5)
    table.add_row("Bono 10Y", f"[{uc}]{_fmt(us10y, suffix='%')}[/{uc}]", "—", "—", "—")

    corr = data.get("Correlation_Proxy")
    abs_c = abs(corr) if corr is not None else None
    cc = _color(abs_c, red_above=0.6, yellow_above=0.3)
    table.add_row("Corr. Sectorial", f"[{cc}]{_fmt(corr, 3)}[/{cc}]", "—", "—", "—")
    return table


def _build_macro_table(data):
    table = Table(title="Valoración y Macro", box=box.SIMPLE_HEAVY, header_style="bold magenta")
    table.add_column("Métrica", style="cyan", no_wrap=True)
    table.add_column("Valor", justify="right")
    table.add_column("Estado", justify="left")

    pe_f = data.get("PE_Forward")
    pe_t = data.get("PE_Trailing")
    pc = _color(pe_f, red_above=25, yellow_above=20)
    pe_source = data.get("PE_Forward_Source")
    pe_label = "PER Forward (USA proxy)" if pe_source else "PER Forward (SPY)"
    pe_status = "Caro" if pe_f and pe_f > 25 else ("Neutro" if pe_f and pe_f > 18 else "Atractivo" if pe_f else "—")
    if pe_f and data.get("PE_Forward_Date"):
        pe_status += f" [dim]({data.get('PE_Forward_Date')})[/dim]"
    table.add_row(pe_label, f"[{pc}]{_fmt(pe_f, 1)}x[/{pc}]", pe_status)
    table.add_row("PER Trailing (SPY)", _fmt(pe_t, 1, "x"), "—")

    m2_chg = data.get("M2_Change_Pct")
    if m2_chg is not None:
        mc = "green" if m2_chg > 0 else "red"
        m2_status = "Expansión" if m2_chg > 0 else "Contracción"
        table.add_row("Liquidez M2 (14 sem.)", f"[{mc}]{m2_chg:+.2f}%[/{mc}]", m2_status)
    else:
        table.add_row("Liquidez M2", "[dim]—[/dim]", "[dim]Requiere FRED_API_KEY[/dim]")

    cpi_yoy = data.get("CPI_YoY_Pct")
    if cpi_yoy is not None:
        ic = _color(cpi_yoy, red_above=4.0, yellow_above=3.0)
        cpi_st = "Alta" if cpi_yoy > 4 else ("Pegajosa" if cpi_yoy > 3 else "Controlada")
        table.add_row("Inflación IPC (YoY)", f"[{ic}]{cpi_yoy:.1f}%[/{ic}]", cpi_st)
    else:
        table.add_row("Inflación IPC", "[dim]—[/dim]", "[dim]Requiere FRED_API_KEY[/dim]")

    return table


def _render_executive_summary(decision, status: MarketStatus):
    favored = ", ".join(decision.favored_assets) if decision.favored_assets else "—"
    action_style = _decision_color(decision.action)
    group = Group(
        Text.from_markup(f"[bold]Acción principal:[/bold] [{action_style}] {decision.action} [/{action_style}]"),
        Text.from_markup(f"[bold]Confianza:[/bold] {decision.confidence}"),
        Text.from_markup(f"[bold]Activos favorecidos:[/bold] {favored}"),
        Text.from_markup(f"[bold]Score general:[/bold] {_score_bar(decision.score)}"),
    )
    status_style = STATUS_COLORS.get(status, "bold white on blue")
    console.print(Panel(group, title="Resumen Ejecutivo", border_style="green", subtitle=f"[{status_style}] Estado: {status.value} [/{status_style}]"))
    console.print("")


def _render_decision(decision):
    allocation = " | ".join(
        f"{asset} {weight}%"
        for asset, weight in decision.allocation.items()
        if weight > 0
    )
    missing = ", ".join(decision.missing_inputs) if decision.missing_inputs else "Ninguno"
    inputs = ", ".join(decision.inputs_used[:10])
    if len(decision.inputs_used) > 10:
        inputs += f" (+{len(decision.inputs_used) - 10} más)"

    body = (
        f"[bold]Motivo principal:[/bold] {decision.rationale}\n"
        f"[bold]Asignación orientativa:[/bold] {allocation}\n\n"
        f"[dim]Inputs usados: {inputs or '—'}[/dim]\n"
        f"[dim]Datos faltantes: {missing}[/dim]"
    )
    console.print(Panel(body, title="Decisión Óptima", border_style="cyan"))


def _render_alerts(alerts, max_alerts: int):
    if not alerts:
        console.print(Panel("[green]Sin anomalías relevantes.[/green]", title="Alertas", border_style="green"))
        console.print("")
        return

    visible = alerts[:max_alerts]
    body = "\n".join(f"• {a}" for a in visible)
    if len(alerts) > max_alerts:
        body += f"\n[dim]... {len(alerts) - max_alerts} alertas adicionales ocultas (usa --max-alerts para ampliar).[/dim]"
    console.print(Panel(body, title="Alertas del Motor Lógico", border_style="yellow"))
    console.print("")


def _render_asset_ranking(decision):
    ranking = sorted(
        decision.asset_scores.items(),
        key=lambda item: item[1].get("score", 0),
        reverse=True,
    )
    table = Table(title="Ranking de Activos", box=box.SIMPLE_HEAVY, header_style="bold magenta")
    table.add_column("Activo", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Barra", justify="left")
    table.add_column("Acción", justify="left")
    table.add_column("Tend.", justify="center")
    table.add_column("Mom. 1M", justify="right")
    table.add_column("Mom. 3M", justify="right")
    table.add_column("Vol. 20D", justify="right")

    for asset, metrics in ranking:
        score = int(metrics.get("score", 0))
        style = _score_style(score)
        table.add_row(
            metrics.get("label", asset),
            f"[{style}]{score}[/{style}]",
            _score_bar(score, width=10),
            metrics.get("action", "—"),
            _trend_symbol(metrics.get("trend", "")),
            _fmt(metrics.get("momentum_1m"), suffix="%"),
            _fmt(metrics.get("momentum_3m"), suffix="%"),
            _fmt(metrics.get("volatility_20d"), suffix="%"),
        )
    console.print(table)
    console.print("")


def _render_news_meta(news_items):
    if not news_items:
        return
    sources = sorted({item.get("source", "RSS") for item in news_items})
    top_sources = ", ".join(sources[:4])
    extra = f" (+{len(sources) - 4} más)" if len(sources) > 4 else ""
    console.print(
        Panel(
            f"[bold]Titulares únicos:[/bold] {len(news_items)}\n"
            f"[bold]Fuentes:[/bold] {top_sources}{extra}",
            title="Resumen de Noticias",
            border_style="magenta",
        )
    )
    console.print("")


def _render_footer(use_news: bool, export_paths, elapsed_s: float):
    line = f"[dim]Tiempo total de actualización: {elapsed_s:.2f}s[/dim]"
    if use_news:
        line += "  [dim]| Noticias activas[/dim]"
    if export_paths:
        line += f"  [dim]| Snapshot: {export_paths['jsonl']}[/dim]"
    if not FRED_API_KEY:
        line += "  [dim]| M2/IPC desactivados (FRED_API_KEY no configurada)[/dim]"
    console.print(line)
    console.print("")


def generate_dashboard(
    use_news: bool = True,
    export: bool = False,
    compact: bool = False,
    max_alerts: int = 8,
    no_clear: bool = False,
):
    """Genera y muestra el dashboard completo."""
    started_at = time.perf_counter()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with console.status("[bold green]Ingiriendo datos y construyendo dashboard...", spinner="dots"):
        data = fetch_market_data()
        news_items = fetch_news_items() if use_news else []
        headlines = [item["title"] for item in news_items]
        engine = LogicEngine(data, headlines=headlines if headlines else None)
        status, alerts = engine.evaluate()
        decision = DecisionEngine(data, status, alerts).evaluate()
        export_paths = export_decision_snapshot(data, decision, news_items) if export else None

    if not no_clear:
        console.clear()

    _render_header(now, status, compact=compact)
    _render_executive_summary(decision, status)
    _render_data_quality(data)

    market = _build_market_table(data)
    macro = _build_macro_table(data)
    console.print(Columns([market, macro], equal=True, expand=True))
    console.print("")

    _render_alerts(alerts, max_alerts=max_alerts)
    _render_decision(decision)
    console.print("")
    _render_asset_ranking(decision)
    if not compact:
        _render_news_meta(news_items)

    elapsed_s = time.perf_counter() - started_at
    _render_footer(use_news, export_paths, elapsed_s)


def main():
    parser = argparse.ArgumentParser(description="NEXUS — Terminal de Análisis Macroeconómico")
    parser.add_argument("--loop", action="store_true", help="Modo loop: refresca periódicamente.")
    parser.add_argument("--interval", type=int, default=REFRESH_INTERVAL_SECONDS,
                        help=f"Segundos entre refrescos (defecto: {REFRESH_INTERVAL_SECONDS}).")
    parser.add_argument("--no-news", action="store_true", help="Desactiva la descarga de noticias RSS.")
    parser.add_argument("--export", action="store_true", help="Guarda snapshot de decisión en data/history.")
    parser.add_argument("--compact", action="store_true", help="Vista compacta con menos paneles secundarios.")
    parser.add_argument("--max-alerts", type=int, default=8, help="Número máximo de alertas a mostrar.")
    parser.add_argument("--no-clear", action="store_true", help="No limpia la pantalla entre refrescos.")
    args = parser.parse_args()

    max_alerts = max(1, args.max_alerts)

    if args.loop:
        console.print(f"[bold cyan]Modo loop activado. Refresco cada {args.interval} segundos.[/bold cyan]")
        console.print("[dim]Presiona Ctrl+C para salir.[/dim]\n")
        while True:
            generate_dashboard(
                use_news=not args.no_news,
                export=args.export,
                compact=args.compact,
                max_alerts=max_alerts,
                no_clear=args.no_clear,
            )
            console.print(f"[dim]Próximo refresco en {args.interval}s. Ctrl+C para salir.[/dim]")
            time.sleep(args.interval)
    else:
        generate_dashboard(
            use_news=not args.no_news,
            export=args.export,
            compact=args.compact,
            max_alerts=max_alerts,
            no_clear=args.no_clear,
        )
        console.print("[dim]Usa --loop para refresco periódico. Ctrl+C para salir.[/dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Saliendo de NEXUS...[/bold red]")
