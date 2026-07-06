"""
Interfaz de Línea de Comandos (main_cli.py)

Dashboard macroeconómico en terminal con foco en claridad visual y trazabilidad.
"""

import sys
import time
import argparse
import json
import hashlib
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
from forex_engine import (
    directional_forex_semaphore,
    forex_dual_perspective,
    forex_semaphore,
    forex_signal,
)
from history import export_decision_snapshot
from logic_engine import LogicEngine, MarketStatus, STATUS_DISPLAY
from risk_filters.news_feed import fetch_news_items
from rotation_engine import RotationEngine

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


def _fmt_signed(val, decimals: int = 2, suffix: str = "%") -> str:
    if val is None:
        return "[dim]—[/dim]"
    style = "green" if val > 0 else ("red" if val < 0 else "white")
    return f"[{style}]{val:+.{decimals}f}{suffix}[/{style}]"


def _to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _trend_from_metrics(metrics):
    price = _to_float(metrics.get("price"))
    ma20 = _to_float(metrics.get("ma20"))
    ma50 = _to_float(metrics.get("ma50"))
    if price is None or ma20 is None or ma50 is None:
        return "n/d"
    if price > ma20 > ma50:
        return "alcista"
    if price < ma20 < ma50:
        return "bajista"
    return "mixta"


def _forex_news_bias(news_items):
    usd_pos = ("hawkish", "higher rates", "inflation sticky", "risk-off", "safe haven", "strong dollar", "dollar strength", "fed hold")
    usd_neg = ("dovish", "rate cuts", "disinflation", "soft data", "weak dollar", "dollar falls", "fed cut")
    eur_pos = ("ecb hawkish", "euro strength", "eurozone inflation up", "eur rallies")
    eur_neg = ("ecb cuts", "eurozone weak", "eurozone recession", "eur weak", "eur drops")

    usd_score = 0
    eur_score = 0
    for item in news_items[:60]:
        title = (item.get("title") or "").lower()
        usd_score += sum(1 for k in usd_pos if k in title)
        usd_score -= sum(1 for k in usd_neg if k in title)
        eur_score += sum(1 for k in eur_pos if k in title)
        eur_score -= sum(1 for k in eur_neg if k in title)

    net = eur_score - usd_score
    if net >= 2:
        expectation = "Sesgo noticias favorece EUR; esperar soporte en EUR/USD."
    elif net <= -2:
        expectation = "Sesgo noticias favorece USD; esperar presión bajista en EUR/USD."
    else:
        expectation = "Sesgo noticias mixto; esperar lateralidad y volatilidad."

    return {
        "usd_score": usd_score,
        "eur_score": eur_score,
        "net_eur_minus_usd": net,
        "expectation": expectation,
    }


def _forex_signal(data, news_items):
    fx = data.get("Forex", {}).get("EURUSD", {})
    uup = data.get("Assets", {}).get("UUP", {})

    eur_1m = _to_float(fx.get("momentum_1m"))
    eur_3m = _to_float(fx.get("momentum_3m"))
    usd_1m = _to_float(uup.get("momentum_1m"))
    usd_3m = _to_float(uup.get("momentum_3m"))

    rel_1m = (eur_1m if eur_1m is not None else 0.0) - (usd_1m if usd_1m is not None else 0.0)
    rel_3m = (eur_3m if eur_3m is not None else 0.0) - (usd_3m if usd_3m is not None else 0.0)
    rel_change = rel_1m - rel_3m

    evolution = "estable"
    if rel_change > 0.7:
        evolution = "EUR gana fuerza frente a USD"
    elif rel_change < -0.7:
        evolution = "USD gana fuerza frente a EUR"

    news = _forex_news_bias(news_items)
    eur_trend = _trend_from_metrics(fx)
    usd_trend = _trend_from_metrics(uup)

    score = 0
    if rel_1m > 0.7:
        score += 2
    elif rel_1m < -0.7:
        score -= 2
    if rel_change > 0.5:
        score += 1
    elif rel_change < -0.5:
        score -= 1
    if eur_trend == "alcista" and usd_trend != "alcista":
        score += 1
    elif usd_trend == "alcista" and eur_trend != "alcista":
        score -= 1
    if news["net_eur_minus_usd"] >= 2:
        score += 1
    elif news["net_eur_minus_usd"] <= -2:
        score -= 1

    if score >= 3:
        action, confidence = "COMPRAR EUR / REDUCIR USD", "ALTA"
    elif score <= -3:
        action, confidence = "COMPRAR USD / REDUCIR EUR", "ALTA"
    elif score >= 1:
        action, confidence = "MANTENER SESGO EUR", "MEDIA"
    elif score <= -1:
        action, confidence = "MANTENER SESGO USD", "MEDIA"
    else:
        action, confidence = "MANTENER / ESPERAR", "BAJA"

    return {
        "fx": fx,
        "uup": uup,
        "score": score,
        "action": action,
        "confidence": confidence,
        "rel_1m": rel_1m,
        "rel_3m": rel_3m,
        "rel_change": rel_change,
        "evolution": evolution,
        "news": news,
        "eur_trend": eur_trend,
        "usd_trend": usd_trend,
    }


def _forex_semaphore(score: int):
    if score >= 3:
        return "[bold white on green] VERDE [/bold white on green]", "Sesgo fuerte pro EUR"
    if score >= 1:
        return "[bold black on yellow] AMARILLO [/bold black on yellow]", "Sesgo moderado pro EUR"
    if score <= -3:
        return "[bold white on red] ROJO [/bold white on red]", "Sesgo fuerte pro USD"
    if score <= -1:
        return "[bold white on magenta] NARANJA [/bold white on magenta]", "Sesgo moderado pro USD"
    return "[bold black on white] NEUTRO [/bold black on white]", "Sin ventaja clara"


def _forex_dual_perspective(fx_sig):
    score = fx_sig["score"]
    if score >= 3:
        eur_view = "COMPRAR EUR/USD"
        usd_view = "REDUCIR USD / evitar largos USD"
    elif score >= 1:
        eur_view = "MANTENER SESGO EUR/USD"
        usd_view = "MANTENER USD bajo control"
    elif score <= -3:
        eur_view = "REDUCIR EUR/USD"
        usd_view = "COMPRAR USD (vs EUR)"
    elif score <= -1:
        eur_view = "MANTENER EUR/USD defensivo"
        usd_view = "MANTENER SESGO USD"
    else:
        eur_view = "MANTENER / ESPERAR"
        usd_view = "MANTENER / ESPERAR"
    return eur_view, usd_view


def _directional_forex_semaphore(score_for_direction: float):
    if score_for_direction >= 2.0:
        return "[bold white on green] VERDE [/bold white on green]", "fuerte"
    if score_for_direction >= 0.5:
        return "[bold black on yellow] AMARILLO [/bold black on yellow]", "moderado"
    if score_for_direction <= -2.0:
        return "[bold white on red] ROJO [/bold white on red]", "fuerte"
    if score_for_direction <= -0.5:
        return "[bold white on magenta] NARANJA [/bold white on magenta]", "moderado"
    return "[bold black on white] NEUTRO [/bold black on white]", "mixto"


def _gauge(value, low: float, high: float, width: int = 18, style: str = "cyan") -> str:
    if value is None:
        return "[dim]" + ("·" * width) + "[/dim]"
    span = max(0.0001, high - low)
    pct = max(0.0, min(1.0, (value - low) / span))
    filled = round(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{style}]{bar}[/{style}]"


def _render_market_pulse(data):
    vix = data.get("VIX")
    us10y = data.get("US10Y")
    cpi = data.get("CPI_YoY_Pct")
    m2 = data.get("M2_Change_Pct")
    corr = data.get("Correlation_Proxy")

    vix_style = _color(vix, red_above=25, yellow_above=16)
    rates_style = _color(us10y, red_above=5.0, yellow_above=4.5)
    cpi_style = _color(cpi, red_above=4.0, yellow_above=3.0)
    m2_style = "green" if (m2 is not None and m2 > 0) else ("red" if m2 is not None else "dim")
    corr_abs = abs(corr) if corr is not None else None
    corr_style = _color(corr_abs, red_above=0.6, yellow_above=0.3)

    body = (
        f"[bold]VIX[/bold]           {_gauge(vix, 10, 40, style=vix_style)}  {_fmt(vix)}\n"
        f"[bold]Bono 10Y[/bold]      {_gauge(us10y, 2, 6, style=rates_style)}  {_fmt(us10y, suffix='%')}\n"
        f"[bold]Inflación IPC[/bold] {_gauge(cpi, 1, 6, style=cpi_style)}  {_fmt(cpi, 1, '%')}\n"
        f"[bold]Liquidez M2[/bold]   {_gauge(m2, -6, 8, style=m2_style)}  {_fmt_signed(m2)}\n"
        f"[bold]Correlación[/bold]   {_gauge(corr_abs, 0, 1, style=corr_style)}  {_fmt(corr, 3)}"
    )
    console.print(Panel(body, title="Pulso de Mercado", border_style="bright_cyan"))
    console.print("")


def _build_snapshot(use_news: bool, export: bool = False):
    data = fetch_market_data()
    news_items = fetch_news_items() if use_news else []
    headlines = [item["title"] for item in news_items]
    engine = LogicEngine(data, headlines=headlines if headlines else None)
    status, alerts = engine.evaluate()
    decision = DecisionEngine(data, status, alerts).evaluate()
    rotation = RotationEngine(data).evaluate()
    export_paths = export_decision_snapshot(data, decision, news_items) if export else None
    return {
        "data": data,
        "news_items": news_items,
        "headlines": headlines,
        "status": status,
        "alerts": alerts,
        "decision": decision,
        "rotation": rotation,
        "export_paths": export_paths,
    }


def _snapshot_signature(snapshot) -> str:
    """Firma estable para saber si merece la pena redibujar el panel."""
    data = snapshot["data"]
    decision = snapshot["decision"]
    rotation = snapshot["rotation"]
    payload = {
        "status": snapshot["status"].value,
        "alerts": snapshot["alerts"],
        "decision": decision.to_dict(),
        "rotation": rotation.to_dict(),
        "market": {
            key: data.get(key)
            for key in (
                "VIX", "VIX_MA5", "VIX_MA10", "VIX_MA20", "US10Y",
                "Correlation_Proxy", "PE_Forward", "PE_Trailing",
                "M2_Change_Pct", "CPI_YoY_Pct",
            )
        },
        "forex": data.get("Forex", {}).get("EURUSD"),
        "usd_proxy": data.get("Assets", {}).get("UUP"),
        "news_titles": [item.get("title") for item in snapshot["news_items"][:25]],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _render_forex(data, news_items, compact: bool = False):
    fx_sig = _forex_signal(data, news_items)
    fx = fx_sig["fx"]
    uup = fx_sig["uup"]
    semaphore_badge, semaphore_text = _forex_semaphore(fx_sig["score"])
    eur_view, usd_view = _forex_dual_perspective(fx_sig)
    eur_badge, eur_strength = _directional_forex_semaphore(fx_sig["rel_1m"])
    usd_badge, usd_strength = _directional_forex_semaphore(-fx_sig["rel_1m"])

    action_style = "bold white on green" if fx_sig["score"] >= 1 else ("bold white on red" if fx_sig["score"] <= -1 else "bold black on yellow")
    body = (
        f"[bold]Semáforo:[/bold] {semaphore_badge}  [dim]{semaphore_text}[/dim]\n"
        f"[bold]Recomendación:[/bold] [{action_style}] {fx_sig['action']} [/{action_style}]  "
        f"[bold]Confianza:[/bold] {fx_sig['confidence']}\n"
        f"[bold]EUR/USD[/bold] {_fmt(fx.get('price'), 4)}  "
        f"1M {_fmt_signed(fx.get('momentum_1m'))}  3M {_fmt_signed(fx.get('momentum_3m'))}  "
        f"Trend {_trend_symbol(fx_sig['eur_trend'])}\n"
        f"[bold]USD (UUP)[/bold] {_fmt(uup.get('price'), 2)}  "
        f"1M {_fmt_signed(uup.get('momentum_1m'))}  3M {_fmt_signed(uup.get('momentum_3m'))}  "
        f"Trend {_trend_symbol(fx_sig['usd_trend'])}\n"
        f"[bold]Dif EUR-USD[/bold] 1M {_fmt_signed(fx_sig['rel_1m'], suffix='pp')} | "
        f"3M {_fmt_signed(fx_sig['rel_3m'], suffix='pp')} | "
        f"Evolución {_fmt_signed(fx_sig['rel_change'], suffix='pp')} ({fx_sig['evolution']})\n"
        f"[bold]Vista EUR->USD:[/bold] {eur_badge} ({eur_strength})  {eur_view}\n"
        f"[bold]Vista USD->EUR:[/bold] {usd_badge} ({usd_strength})  {usd_view}\n"
    )
    if compact:
        body += f"[dim]{fx_sig['news']['expectation']}[/dim]"
    else:
        body += (
            f"[bold]News bias[/bold] EUR {fx_sig['news']['eur_score']:+d} | "
            f"USD {fx_sig['news']['usd_score']:+d} | "
            f"Neto {fx_sig['news']['net_eur_minus_usd']:+d}\n"
            f"[dim]{fx_sig['news']['expectation']}[/dim]"
        )
    console.print(Panel(body, title="Sección Forex (USD / EUR)", border_style="bright_magenta"))
    console.print("")


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


def _render_decision(decision, compact: bool = False):
    allocation = " | ".join(
        f"{asset} {weight}%"
        for asset, weight in decision.allocation.items()
        if weight > 0
    )
    missing = ", ".join(decision.missing_inputs) if decision.missing_inputs else "Ninguno"
    max_inputs = 6 if compact else 10
    inputs = ", ".join(decision.inputs_used[:max_inputs])
    if len(decision.inputs_used) > max_inputs:
        inputs += f" (+{len(decision.inputs_used) - max_inputs} más)"

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


def _render_rotation(rotation, compact: bool = False):
    state_style = {
        "ROTACIÓN ACTIVA Y SANA": "bold white on green",
        "ROTACIÓN HACIA REZAGADOS": "bold black on yellow",
        "LIDERAZGO TECH DOMINANTE": "bold white on blue",
        "DESCANSO SIN RELEVO CLARO": "bold white on red",
        "SIN DATOS": "bold white on blue",
    }.get(rotation.state, "bold black on yellow")

    leaders = _fmt_signed(rotation.leaders_avg_1m)
    receivers = _fmt_signed(rotation.receivers_avg_1m)
    console.print(
        Panel(
            f"[{state_style}] {rotation.state} [/{state_style}]\n"
            f"[bold]Lectura:[/bold] {rotation.summary}\n"
            f"[dim]Momentum medio 1M líderes IA/semis/tech: {leaders} | "
            f"receptores biotech/salud/seguros: {receivers}[/dim]",
            title="Mapa de Rotación Sectorial",
            border_style="bright_blue",
        )
    )

    leaders = [theme for theme in rotation.themes if theme.group == "Líderes en descanso"]
    receivers = [theme for theme in rotation.themes if theme.group == "Receptores de flujo"]
    console.print(_build_rotation_table("Descansa / sale dinero", leaders, "bright_yellow", compact=compact))
    console.print(_build_rotation_table("Entra / recibe flujo", receivers, "bright_green", compact=compact))
    console.print("")


def _short_signal(signal: str) -> str:
    replacements = {
        "Descanso sano tras liderazgo": "Descanso sano",
        "Corrección activa": "Corrigiendo",
        "Liderazgo aún fuerte": "Lidera aún",
        "Base en formación": "Formando base",
        "Entrada clara de flujo": "Flujo claro",
        "Mejora incipiente": "Mejora inicial",
        "Mantiene estructura": "Estructura ok",
        "Aún sin confirmación": "Sin confirmar",
    }
    return replacements.get(signal, signal)


def _short_represents(text: str) -> str:
    shortcuts = {
        "nube, centros de datos, software y hardware ligados a IA": "nube/data centers/IA",
        "Nvidia, AMD, Broadcom, TSMC y fabricantes de chips": "chips y semis",
        "mega caps tech, software, hardware y plataformas": "mega tech/software",
        "biotech de alto beta, innovación médica y rezagados de salud": "biotech alto beta",
        "healthcare defensivo, pharma grande y servicios médicos": "salud defensiva/pharma",
        "aseguradoras y financieras defensivas sensibles a tipos": "aseguradoras",
        "pharma especializada y compañías de medicamentos": "farmacéuticas",
    }
    return shortcuts.get(text, text)


def _build_rotation_table(title: str, themes, border_style: str, compact: bool = False):
    table = Table(title=title, box=box.SIMPLE_HEAVY, header_style="bold magenta", border_style=border_style)
    table.add_column("Tema", style="bold white", no_wrap=True)
    table.add_column("ETF", justify="center", style="cyan", no_wrap=True)
    table.add_column("Señal", style="yellow", no_wrap=True)
    table.add_column("1M", justify="right", no_wrap=True)
    if not compact:
        table.add_column("3M", justify="right", no_wrap=True)
    table.add_column("vs SPY", justify="right", no_wrap=True)

    rows = themes[:3] if compact else themes
    for theme in rows:
        cells = [
            theme.theme,
            theme.ticker,
            f"{_trend_symbol(theme.trend)} {_short_signal(theme.signal)}",
            _fmt_signed(theme.momentum_1m),
        ]
        if not compact:
            cells.append(_fmt_signed(theme.momentum_3m))
        cells.append(_fmt_signed(theme.relative_1m_vs_spy))
        table.add_row(*cells)
    return table


def _render_asset_ranking(decision, compact: bool = False):
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
    if not compact:
        table.add_column("Mom. 3M", justify="right")
        table.add_column("Vol. 20D", justify="right")

    rows = ranking[:5] if compact else ranking
    for asset, metrics in rows:
        score = int(metrics.get("score", 0))
        style = _score_style(score)
        cells = [
            metrics.get("label", asset),
            f"[{style}]{score}[/{style}]",
            _score_bar(score, width=8 if compact else 10),
        ]
        cells.extend([
            metrics.get("action", "—"),
            _trend_symbol(metrics.get("trend", "")),
            _fmt_signed(metrics.get("momentum_1m")),
        ])
        if not compact:
            cells.append(_fmt_signed(metrics.get("momentum_3m")))
            cells.append(_fmt(metrics.get("volatility_20d"), suffix="%"))
        table.add_row(*cells)
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


def _render_dashboard(
    snapshot,
    now: str,
    use_news: bool,
    compact: bool,
    max_alerts: int,
    no_clear: bool,
    elapsed_s: float,
):
    data = snapshot["data"]
    news_items = snapshot["news_items"]
    status = snapshot["status"]
    alerts = snapshot["alerts"]
    decision = snapshot["decision"]
    rotation = snapshot["rotation"]
    export_paths = snapshot["export_paths"]

    if not no_clear:
        console.clear()

    _render_header(now, status, compact=compact)
    _render_executive_summary(decision, status)
    _render_data_quality(data)
    _render_market_pulse(data)

    market = _build_market_table(data)
    macro = _build_macro_table(data)
    console.print(Columns([market, macro], equal=True, expand=True))
    console.print("")
    _render_forex(data, news_items, compact=compact)

    _render_rotation(rotation, compact=compact)
    _render_alerts(alerts, max_alerts=max_alerts)
    _render_decision(decision, compact=compact)
    console.print("")
    _render_asset_ranking(decision, compact=compact)
    if not compact:
        _render_news_meta(news_items)

    _render_footer(use_news, export_paths, elapsed_s)


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
        snapshot = _build_snapshot(use_news=use_news, export=export)

    elapsed_s = time.perf_counter() - started_at
    _render_dashboard(
        snapshot=snapshot,
        now=now,
        use_news=use_news,
        compact=compact,
        max_alerts=max_alerts,
        no_clear=no_clear,
        elapsed_s=elapsed_s,
    )
    return snapshot


def _run_live_loop(use_news: bool, export: bool, compact: bool, max_alerts: int, no_clear: bool, interval: int):
    last_signature = None
    while True:
        started_at = time.perf_counter()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with console.status("[bold green]Actualizando NEXUS...", spinner="dots"):
            snapshot = _build_snapshot(use_news=use_news, export=export)
        signature = _snapshot_signature(snapshot)
        elapsed_s = time.perf_counter() - started_at

        if signature != last_signature:
            _render_dashboard(
                snapshot=snapshot,
                now=now,
                use_news=use_news,
                compact=compact,
                max_alerts=max_alerts,
                no_clear=no_clear,
                elapsed_s=elapsed_s,
            )
            console.print(
                f"[dim]Auto-loop activo: próxima comprobación en {interval}s. "
                "Solo se redibuja si cambia la lectura. Ctrl+C para salir.[/dim]"
            )
            last_signature = signature
        else:
            console.print(f"[dim]{now} | Sin cambios relevantes. Próxima comprobación en {interval}s.[/dim]")

        time.sleep(interval)


def _detail_table(title: str):
    table = Table(title=title, box=box.SIMPLE_HEAVY, header_style="bold magenta")
    table.add_column("Campo", style="cyan", no_wrap=True)
    table.add_column("Valor")
    return table


def _show_detail_menu(snapshot):
    while True:
        console.print(Panel(
            "[bold]Detalle NEXUS[/bold]\n"
            "1. Mercado y macro\n"
            "2. Decisión y asignación\n"
            "3. Rotación sectorial\n"
            "4. Forex (USD/EUR)\n"
            "5. Ranking de activos\n"
            "6. Noticias y fuentes\n"
            "7. Calidad de datos\n\n"
            "Pulsa Enter para volver al dashboard. Escribe q para salir.",
            title="Menú de detalle",
            border_style="cyan",
        ))
        choice = input("Detalle [1-7, Enter=volver, q=salir]: ").strip().lower()
        if choice == "":
            return
        if choice == "q":
            raise KeyboardInterrupt

        data = snapshot["data"]
        decision = snapshot["decision"]
        rotation = snapshot["rotation"]
        news_items = snapshot["news_items"]

        if choice == "1":
            table = _detail_table("Mercado y Macro")
            for key in ("VIX", "VIX_MA5", "VIX_MA10", "VIX_MA20", "US10Y", "Correlation_Proxy",
                        "PE_Forward", "PE_Forward_Source", "PE_Forward_Date", "PE_Trailing",
                        "M2_Change_Pct", "CPI_YoY_Pct"):
                table.add_row(key, str(data.get(key, "—")))
            console.print(table)
        elif choice == "2":
            table = _detail_table("Decisión y Asignación")
            table.add_row("Acción", decision.action)
            table.add_row("Score", str(decision.score))
            table.add_row("Confianza", decision.confidence)
            table.add_row("Favorecidos", ", ".join(decision.favored_assets))
            table.add_row("Asignación", json.dumps(decision.allocation, ensure_ascii=False))
            table.add_row("Motivo", decision.rationale)
            table.add_row("Inputs", ", ".join(decision.inputs_used))
            console.print(table)
        elif choice == "3":
            _render_rotation(rotation)
        elif choice == "4":
            _render_forex(data, news_items, compact=False)
        elif choice == "5":
            _render_asset_ranking(decision)
        elif choice == "6":
            table = _detail_table("Noticias")
            table.add_row("Titulares únicos", str(len(news_items)))
            table.add_row("Fuentes", ", ".join(sorted({item.get("source", "RSS") for item in news_items})))
            for item in news_items[:12]:
                table.add_row(item.get("source", "RSS"), item.get("title", "—"))
            console.print(table)
        elif choice == "7":
            table = _detail_table("Calidad de Datos")
            for key, meta in data.get("DataQuality", {}).items():
                table.add_row(key, f"{meta.get('status')} | {meta.get('source')} | {meta.get('detail', '')}")
            console.print(table)
        else:
            console.print("[yellow]Opción no reconocida.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="NEXUS — Terminal de Análisis Macroeconómico")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola actualización y termina.")
    parser.add_argument("--loop", action="store_true", help="Modo loop explícito. Es el comportamiento por defecto.")
    parser.add_argument("--interval", type=int, default=REFRESH_INTERVAL_SECONDS,
                        help=f"Segundos entre refrescos (defecto: {REFRESH_INTERVAL_SECONDS}).")
    parser.add_argument("--no-news", action="store_true", help="Desactiva la descarga de noticias RSS.")
    parser.add_argument("--export", action="store_true", help="Guarda snapshot de decisión en data/history.")
    parser.add_argument("--compact", action="store_true", help="Vista compacta (compatibilidad).")
    parser.add_argument("--full-view", action="store_true", help="Fuerza vista completa con todas las tablas.")
    parser.add_argument("--max-alerts", type=int, default=8, help="Número máximo de alertas a mostrar.")
    parser.add_argument("--no-clear", action="store_true", help="No limpia la pantalla entre refrescos.")
    parser.add_argument("--details", action="store_true", help="Abre un menú interactivo de detalle tras cargar el dashboard.")
    args = parser.parse_args()

    compact_mode = True
    if args.full_view:
        compact_mode = False
    if args.compact:
        compact_mode = True

    max_alerts = max(1, args.max_alerts)
    if compact_mode and args.max_alerts == 8:
        max_alerts = 3

    if args.once or args.details:
        snapshot = generate_dashboard(
            use_news=not args.no_news,
            export=args.export,
            compact=compact_mode,
            max_alerts=max_alerts,
            no_clear=args.no_clear,
        )
        if args.details:
            _show_detail_menu(snapshot)
        else:
            console.print("[dim]Usa el modo por defecto para auto-loop. Ctrl+C para salir.[/dim]")
        return

    console.print(f"[bold cyan]Auto-loop activado. Comprobación cada {args.interval} segundos.[/bold cyan]")
    console.print("[dim]NEXUS solo redibuja cuando cambia la lectura. Ctrl+C para salir.[/dim]\n")
    _run_live_loop(
        use_news=not args.no_news,
        export=args.export,
        compact=compact_mode,
        max_alerts=max_alerts,
        no_clear=args.no_clear,
        interval=max(10, args.interval),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Saliendo de NEXUS...[/bold red]")
