"""
NEXUS Workstation Desktop (local app).

Interfaz local nativa (tkinter) con estilo funcional tipo terminal/Bloomberg:
- barra superior de navegación
- refresco automático cada 5 minutos
- solo redibuja si cambia la lectura
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import font as tkfont
from typing import Any, Dict

from decision_engine import DecisionEngine
from history import export_decision_snapshot
from logic_engine import LogicEngine
from risk_filters.news_feed import fetch_news_items
from rotation_engine import RotationEngine
from data_ingestion import fetch_market_data


REFRESH_MS = 5 * 60 * 1000

BG = "#05070B"
PANEL = "#0B0F17"
PANEL_ALT = "#101625"
TEXT = "#D7DEE9"
MUTED = "#8D9BB0"
LINE = "#293245"
ACCENT = "#3ED6FF"
GOOD = "#36C26A"
WARN = "#F7C948"
BAD = "#EF4F68"


def _configure_windows_dpi_awareness() -> None:
    """Mejora nitidez en Windows HiDPI para evitar look pixelado."""
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_snapshot(use_news: bool = True, export: bool = False) -> Dict[str, Any]:
    data = fetch_market_data()
    news_items = fetch_news_items() if use_news else []
    headlines = [item["title"] for item in news_items]

    logic = LogicEngine(data, headlines=headlines if headlines else None)
    status, alerts = logic.evaluate()
    decision = DecisionEngine(data, status, alerts).evaluate()
    rotation = RotationEngine(data).evaluate()
    export_paths = export_decision_snapshot(data, decision, news_items) if export else None

    return {
        "captured_at_utc": _now_utc_iso(),
        "status": status.value,
        "alerts": alerts,
        "data": data,
        "decision": decision.to_dict(),
        "rotation": rotation.to_dict(),
        "news_items": news_items,
        "export_paths": export_paths,
    }


def snapshot_signature(snapshot: Dict[str, Any]) -> str:
    payload = {
        "status": snapshot["status"],
        "alerts": snapshot["alerts"],
        "decision": snapshot["decision"],
        "rotation": snapshot["rotation"],
        "market": {
            key: snapshot["data"].get(key)
            for key in (
                "VIX",
                "US10Y",
                "Correlation_Proxy",
                "PE_Forward",
                "PE_Trailing",
                "M2_Change_Pct",
                "CPI_YoY_Pct",
            )
        },
        "forex": snapshot["data"].get("Forex", {}).get("EURUSD"),
        "news_titles": [item.get("title") for item in snapshot["news_items"][:30]],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fmt(value, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{float(value):.{decimals}f}{suffix}"


def signed(value, decimals: int = 2, suffix: str = "%") -> str:
    if value is None:
        return "—"
    value = float(value)
    return f"{value:+.{decimals}f}{suffix}"


def score_bar(score: int, width: int = 14) -> str:
    score = max(0, min(100, int(score)))
    filled = round((score / 100.0) * width)
    return "█" * filled + "░" * (width - filled)


def score_tag(score: int) -> str:
    if score >= 75:
        return "score_green"
    if score >= 45:
        return "score_yellow"
    return "score_red"


def metric_bar(value: float | None, low: float, high: float, width: int = 12) -> str:
    if value is None:
        return "·" * width
    span = max(0.0001, high - low)
    pct = max(0.0, min(1.0, (float(value) - low) / span))
    filled = round(width * pct)
    return "█" * filled + "░" * (width - filled)


def trend_from_metrics(metrics: Dict[str, Any]) -> str:
    price = metrics.get("price")
    ma20 = metrics.get("ma20")
    ma50 = metrics.get("ma50")
    if price is None or ma20 is None or ma50 is None:
        return "n/d"
    if price > ma20 > ma50:
        return "alcista"
    if price < ma20 < ma50:
        return "bajista"
    return "mixta"


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def forex_news_bias(news_items: list[Dict[str, Any]]) -> Dict[str, Any]:
    usd_pos = ["hawkish", "higher rates", "inflation sticky", "risk-off", "safe haven", "strong dollar", "dollar strength", "fed hold"]
    usd_neg = ["dovish", "rate cuts", "disinflation", "soft data", "weak dollar", "dollar falls", "fed cut"]
    eur_pos = ["ecb hawkish", "euro strength", "eurozone inflation up", "eur rallies"]
    eur_neg = ["ecb cuts", "eurozone weak", "eurozone recession", "eur weak", "eur drops"]

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
        expectation = "Sesgo noticias: favorece EUR. Esperar soporte en EUR/USD."
    elif net <= -2:
        expectation = "Sesgo noticias: favorece USD. Esperar presion bajista en EUR/USD."
    else:
        expectation = "Sesgo noticias mixto. Esperar lateralidad y volatilidad por eventos."

    return {
        "usd_score": usd_score,
        "eur_score": eur_score,
        "net_eur_minus_usd": net,
        "expectation": expectation,
    }


def forex_signal(fx_metrics: Dict[str, Any], uup_metrics: Dict[str, Any], news_items: list[Dict[str, Any]]) -> Dict[str, Any]:
    eur_1m = _to_float(fx_metrics.get("momentum_1m"))
    eur_3m = _to_float(fx_metrics.get("momentum_3m"))
    usd_1m = _to_float(uup_metrics.get("momentum_1m"))
    usd_3m = _to_float(uup_metrics.get("momentum_3m"))
    eur_trend = trend_from_metrics(fx_metrics)
    usd_trend = trend_from_metrics(uup_metrics)

    rel_1m = (eur_1m if eur_1m is not None else 0.0) - (usd_1m if usd_1m is not None else 0.0)
    rel_3m = (eur_3m if eur_3m is not None else 0.0) - (usd_3m if usd_3m is not None else 0.0)
    rel_change = rel_1m - rel_3m

    evolution = "estable"
    if rel_change > 0.7:
        evolution = "EUR gana fuerza frente a USD"
    elif rel_change < -0.7:
        evolution = "USD gana fuerza frente a EUR"

    news = forex_news_bias(news_items)

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
        action = "COMPRAR EUR / REDUCIR USD"
        confidence = "ALTA"
    elif score <= -3:
        action = "COMPRAR USD / REDUCIR EUR"
        confidence = "ALTA"
    elif score >= 1:
        action = "MANTENER SESGO EUR"
        confidence = "MEDIA"
    elif score <= -1:
        action = "MANTENER SESGO USD"
        confidence = "MEDIA"
    else:
        action = "MANTENER / ESPERAR"
        confidence = "BAJA"

    return {
        "action": action,
        "confidence": confidence,
        "score": score,
        "eur_trend": eur_trend,
        "usd_trend": usd_trend,
        "rel_1m": rel_1m,
        "rel_3m": rel_3m,
        "rel_change": rel_change,
        "evolution": evolution,
        "news": news,
    }


def forex_dual_perspective(sig: Dict[str, Any]) -> Dict[str, str]:
    score = sig.get("score", 0)
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
    return {"eur_view": eur_view, "usd_view": usd_view}


def directional_forex_semaphore(score_for_direction: float) -> Dict[str, str]:
    if score_for_direction >= 2.0:
        return {"badge": "🟢 VERDE", "strength": "fuerte"}
    if score_for_direction >= 0.5:
        return {"badge": "🟡 AMARILLO", "strength": "moderado"}
    if score_for_direction <= -2.0:
        return {"badge": "🔴 ROJO", "strength": "fuerte"}
    if score_for_direction <= -0.5:
        return {"badge": "🟠 NARANJA", "strength": "moderado"}
    return {"badge": "⚪ NEUTRO", "strength": "mixto"}


class NexusDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NEXUS Workstation")
        self.root.configure(bg=BG)
        self.root.geometry("1380x860")
        self.root.minsize(1100, 700)

        self._configure_tk_scaling()
        mono = self._pick_font_family(("Cascadia Mono", "Consolas", "Courier New"))
        self.ui_font = tkfont.Font(family=mono, size=11)
        self.title_font = tkfont.Font(family=mono, size=12, weight="bold")
        self.current_snapshot: Dict[str, Any] | None = None
        self.current_signature: str | None = None
        self.current_view = "overview"
        self.fetch_in_progress = False

        self._build_ui()
        self._schedule_fetch(immediate=True)

    def _pick_font_family(self, candidates: tuple[str, ...]) -> str:
        available = set(tkfont.families(self.root))
        for family in candidates:
            if family in available:
                return family
        return "TkFixedFont"

    def _configure_tk_scaling(self) -> None:
        # Ajusta escala lógica según DPI real para texto más nítido.
        try:
            pixels_per_inch = float(self.root.winfo_fpixels("1i"))
            scaling = max(1.0, pixels_per_inch / 96.0)
            self.root.tk.call("tk", "scaling", scaling)
        except Exception:
            pass

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#070B13", bd=0, highlightthickness=0)
        top.pack(fill="x")

        brand = tk.Label(top, text="NEXUS WORKSTATION", fg=ACCENT, bg="#070B13", font=self.title_font, padx=12, pady=10)
        brand.pack(side="left")

        nav = tk.Frame(top, bg="#070B13")
        nav.pack(side="left", padx=8)
        self.nav_buttons = {}
        for key, label in [
            ("overview", "Overview"),
            ("rotation", "Rotación"),
            ("forex", "Forex"),
            ("assets", "Activos"),
            ("news", "Noticias"),
            ("quality", "Data Quality"),
        ]:
            btn = tk.Button(
                nav,
                text=label,
                command=lambda k=key: self._set_view(k),
                fg=MUTED,
                bg=PANEL,
                activeforeground=TEXT,
                activebackground=PANEL_ALT,
                relief="flat",
                padx=10,
                pady=4,
                font=self.ui_font,
            )
            btn.pack(side="left", padx=4)
            self.nav_buttons[key] = btn

        right = tk.Frame(top, bg="#070B13")
        right.pack(side="right", padx=12)
        self.status_label = tk.Label(right, text="Cargando...", fg=TEXT, bg=PANEL, font=self.ui_font, padx=8, pady=4)
        self.status_label.pack(side="left", padx=6)
        self.updated_label = tk.Label(right, text="--", fg=MUTED, bg="#070B13", font=self.ui_font)
        self.updated_label.pack(side="left")

        body = tk.Frame(self.root, bg=BG, padx=12, pady=10)
        body.pack(fill="both", expand=True)

        self.view_title = tk.Label(body, text="Overview", fg=ACCENT, bg=BG, font=self.title_font, anchor="w")
        self.view_title.pack(fill="x", pady=(0, 8))

        self.text = tk.Text(
            body,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#243148",
            relief="flat",
            wrap="none",
            font=self.ui_font,
            padx=12,
            pady=10,
        )
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("score_green", foreground=GOOD)
        self.text.tag_configure("score_yellow", foreground=WARN)
        self.text.tag_configure("score_red", foreground=BAD)

        footer = tk.Frame(self.root, bg="#070B13")
        footer.pack(fill="x")
        self.footer_left = tk.Label(footer, text="Auto-refresh 5m • solo cambia cuando hay cambios", fg=MUTED, bg="#070B13", font=self.ui_font)
        self.footer_left.pack(side="left", padx=12, pady=8)
        self.footer_right = tk.Label(footer, text="sig: --", fg=MUTED, bg="#070B13", font=self.ui_font)
        self.footer_right.pack(side="right", padx=12, pady=8)

        refresh_btn = tk.Button(
            footer,
            text="Refrescar ahora",
            command=lambda: self._schedule_fetch(immediate=True),
            fg=TEXT,
            bg=PANEL,
            activeforeground=TEXT,
            activebackground=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=4,
            font=self.ui_font,
        )
        refresh_btn.pack(side="right", padx=8)

        self._set_view("overview")

    def _set_view(self, key: str):
        self.current_view = key
        for k, btn in self.nav_buttons.items():
            btn.configure(fg=TEXT if k == key else MUTED, bg=PANEL_ALT if k == key else PANEL)
        self.view_title.configure(text=self.nav_buttons[key]["text"])
        self._render_current()

    def _schedule_fetch(self, immediate: bool = False):
        if immediate:
            self._start_fetch()
        self.root.after(REFRESH_MS, self._schedule_fetch)

    def _start_fetch(self):
        if self.fetch_in_progress:
            return
        self.fetch_in_progress = True
        self.status_label.configure(text="Actualizando...", fg=TEXT, bg=PANEL)
        t = threading.Thread(target=self._fetch_worker, daemon=True)
        t.start()

    def _fetch_worker(self):
        try:
            snap = build_snapshot(use_news=True, export=False)
            sig = snapshot_signature(snap)
            self.root.after(0, lambda: self._on_fetch_success(snap, sig))
        except Exception as exc:
            self.root.after(0, lambda: self._on_fetch_error(exc))

    def _on_fetch_success(self, snap: Dict[str, Any], sig: str):
        changed = sig != self.current_signature
        self.fetch_in_progress = False
        self.updated_label.configure(text=snap.get("captured_at_utc", "--"))
        self.footer_right.configure(text=f"sig: {sig[:12]}")

        if changed:
            self.current_snapshot = snap
            self.current_signature = sig
            self.status_label.configure(text=f"{snap['status']} • actualizado", fg=TEXT, bg="#143726")
            self._render_current()
        else:
            self.status_label.configure(text=f"{snap['status']} • sin cambios", fg=TEXT, bg="#243148")

    def _on_fetch_error(self, exc: Exception):
        self.fetch_in_progress = False
        self.status_label.configure(text=f"ERROR: {exc}", fg=TEXT, bg="#4A1F2A")

    def _render_current(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not self.current_snapshot:
            self.text.insert("1.0", "Cargando snapshot...\n")
            self.text.configure(state="disabled")
            return

        if self.current_view == "assets":
            self._render_assets_colored(self.current_snapshot)
            self.text.configure(state="disabled")
            return

        view_renderers = {
            "overview": self._render_overview,
            "rotation": self._render_rotation,
            "forex": self._render_forex,
            "news": self._render_news,
            "quality": self._render_quality,
        }
        content = view_renderers[self.current_view](self.current_snapshot)
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")

    def _render_overview(self, s: Dict[str, Any]) -> str:
        d = s["data"]
        dec = s["decision"]
        rot = s["rotation"]
        fx = d.get("Forex", {}).get("EURUSD", {})
        uup_metrics = d.get("Assets", {}).get("UUP", {})
        fx_sig = forex_signal(fx, uup_metrics, s.get("news_items", []))
        dual = forex_dual_perspective(fx_sig)
        eur_sem = directional_forex_semaphore(fx_sig["rel_1m"])
        usd_sem = directional_forex_semaphore(-fx_sig["rel_1m"])
        ranked = sorted(
            dec.get("asset_scores", {}).values(),
            key=lambda item: item.get("score", 0),
            reverse=True,
        )[:3]
        top_news = s.get("news_items", [])[:3]
        lines = [
            f"STATUS: {s['status']}    SNAPSHOT UTC: {s.get('captured_at_utc', '--')}",
            "",
            "DECISION",
            f"  Accion      : {dec['action']}",
            f"  Score       : {dec['score']}/100  {score_bar(int(dec['score']), 16)}",
            f"  Confianza   : {dec['confidence']}",
            f"  Favorecidos : {', '.join(dec['favored_assets'])}",
            "",
            "PULSO MERCADO",
            f"  VIX          {metric_bar(d.get('VIX'), 10, 40)}  {fmt(d.get('VIX'))}",
            f"  Bono 10Y     {metric_bar(d.get('US10Y'), 2, 6)}  {fmt(d.get('US10Y'), 2, '%')}",
            f"  Inflacion    {metric_bar(d.get('CPI_YoY_Pct'), 1, 6)}  {fmt(d.get('CPI_YoY_Pct'), 1, '%')}",
            f"  Liquidez M2  {metric_bar(d.get('M2_Change_Pct'), -6, 8)}  {signed(d.get('M2_Change_Pct'))}",
            f"  Correlacion  {metric_bar(abs(d.get('Correlation_Proxy')) if d.get('Correlation_Proxy') is not None else None, 0, 1)}  {fmt(d.get('Correlation_Proxy'), 3)}",
            "",
            "ROTACION",
            f"  Estado       : {rot['state']}",
            f"  Leaders 1M   : {signed(rot.get('leaders_avg_1m'))}",
            f"  Receivers 1M : {signed(rot.get('receivers_avg_1m'))}",
            "",
            "FOREX (USD / EUR)",
            f"  EUR/USD spot : {fmt(fx.get('price'), 4)}",
            f"  EUR/USD 1M   : {signed(fx.get('momentum_1m'))}",
            f"  EUR/USD 3M   : {signed(fx.get('momentum_3m'))}",
            f"  USD (UUP) 1M : {signed(uup_metrics.get('momentum_1m'))}",
            f"  USD trend    : {trend_from_metrics(uup_metrics)}",
            f"  Dif EUR-USD 1M: {signed(fx_sig['rel_1m'], suffix='pp')}",
            f"  Evolucion dif : {signed(fx_sig['rel_change'], suffix='pp')} ({fx_sig['evolution']})",
            f"  Accion FX     : {fx_sig['action']} [{fx_sig['confidence']}]",
            f"  Vista EUR->USD: {eur_sem['badge']} ({eur_sem['strength']})  {dual['eur_view']}",
            f"  Vista USD->EUR: {usd_sem['badge']} ({usd_sem['strength']})  {dual['usd_view']}",
            f"  Que esperar   : {fx_sig['news']['expectation']}",
            "",
            "TOP ACTIVOS",
        ]
        for m in ranked:
            sc = int(m.get("score", 0))
            lines.append(
                f"  {m.get('label', '-'):<14} {sc:>3}/100  {score_bar(sc, 10)}  "
                f"{(m.get('action') or '-'):<10} {signed(m.get('momentum_1m'))}"
            )
        lines.extend(["", "ALERTAS CLAVE"])
        for alert in s["alerts"][:4]:
            lines.append(f"  - {alert}")
        if len(s["alerts"]) > 4:
            lines.append(f"  ... {len(s['alerts']) - 4} alertas adicionales.")
        lines.extend(["", "NEWS FLOW"])
        for item in top_news:
            lines.append(f"  - [{item.get('source', 'RSS')}] {item.get('title', '-')}")
        if len(s.get("news_items", [])) > 3:
            lines.append(f"  ... {len(s['news_items']) - 3} titulares adicionales.")
        return "\n".join(lines)

    def _render_rotation(self, s: Dict[str, Any]) -> str:
        r = s["rotation"]
        lines = [
            f"ESTADO ROTACION: {r['state']}",
            f"LECTURA        : {r['summary']}",
            f"LEADERS 1M     : {signed(r.get('leaders_avg_1m'))}",
            f"RECEIVERS 1M   : {signed(r.get('receivers_avg_1m'))}",
            "",
            "MAPA",
            "GROUP                  THEME                     ETF   SIGNAL                 1M       VS_SPY",
            "-" * 95,
        ]
        for t in r["themes"]:
            group = "DESCANSA/SALE" if t["group"] == "Líderes en descanso" else "ENTRA/RECIBE"
            lines.append(
                f"{group:<22}{t['theme']:<25}{t['ticker']:<6}{t['signal'][:20]:<22}"
                f"{signed(t.get('momentum_1m')):<9}{signed(t.get('relative_1m_vs_spy'))}"
            )
            lines.append(f"  -> {t['represents']}")
        return "\n".join(lines)

    def _render_forex(self, s: Dict[str, Any]) -> str:
        d = s["data"]
        fx = d.get("Forex", {}).get("EURUSD", {})
        uup_metrics = d.get("Assets", {}).get("UUP", {})
        uup_score = s["decision"].get("asset_scores", {}).get("UUP", {}).get("score")
        fx_sig = forex_signal(fx, uup_metrics, s.get("news_items", []))
        dual = forex_dual_perspective(fx_sig)
        eur_sem = directional_forex_semaphore(fx_sig["rel_1m"])
        usd_sem = directional_forex_semaphore(-fx_sig["rel_1m"])
        lines = [
            "FOREX DASHBOARD (USD / EUR)",
            "",
            "EUR/USD",
            f"  Spot           : {fmt(fx.get('price'), 4)}",
            f"  MA20 / MA50    : {fmt(fx.get('ma20'), 4)} / {fmt(fx.get('ma50'), 4)}",
            f"  Trend          : {fx_sig['eur_trend']}",
            f"  Momentum 1M    : {signed(fx.get('momentum_1m'))}  {metric_bar(fx.get('momentum_1m'), -5, 5)}",
            f"  Momentum 3M    : {signed(fx.get('momentum_3m'))}  {metric_bar(fx.get('momentum_3m'), -10, 10)}",
            f"  Volatilidad 20d: {fmt(fx.get('volatility_20d'), 2, '%')}",
            "",
            "USD (proxy UUP)",
            f"  Spot           : {fmt(uup_metrics.get('price'), 2)}",
            f"  MA20 / MA50    : {fmt(uup_metrics.get('ma20'), 2)} / {fmt(uup_metrics.get('ma50'), 2)}",
            f"  Trend          : {fx_sig['usd_trend']}",
            f"  Momentum 1M    : {signed(uup_metrics.get('momentum_1m'))}  {metric_bar(uup_metrics.get('momentum_1m'), -5, 5)}",
            f"  Momentum 3M    : {signed(uup_metrics.get('momentum_3m'))}  {metric_bar(uup_metrics.get('momentum_3m'), -10, 10)}",
            f"  Score operativo: {uup_score if uup_score is not None else '—'}/100",
            "",
            "CAMBIO RELATIVO EUR vs USD",
            f"  Dif 1M (EUR-USD): {signed(fx_sig['rel_1m'], suffix='pp')}  {metric_bar(fx_sig['rel_1m'], -5, 5)}",
            f"  Dif 3M (EUR-USD): {signed(fx_sig['rel_3m'], suffix='pp')}  {metric_bar(fx_sig['rel_3m'], -10, 10)}",
            f"  Cambio del dif  : {signed(fx_sig['rel_change'], suffix='pp')} -> {fx_sig['evolution']}",
            "",
            "OPERATIVA",
            f"  Recomendacion   : {fx_sig['action']}",
            f"  Confianza       : {fx_sig['confidence']} (score {fx_sig['score']:+d})",
            f"  Vista EUR->USD  : {eur_sem['badge']} ({eur_sem['strength']})  {dual['eur_view']}",
            f"  Vista USD->EUR  : {usd_sem['badge']} ({usd_sem['strength']})  {dual['usd_view']}",
            "",
            "NEWS BIAS",
            f"  EUR score       : {fx_sig['news']['eur_score']:+d}",
            f"  USD score       : {fx_sig['news']['usd_score']:+d}",
            f"  Neto EUR-USD    : {fx_sig['news']['net_eur_minus_usd']:+d}",
            f"  Que esperar     : {fx_sig['news']['expectation']}",
        ]
        return "\n".join(lines)

    def _render_assets(self, s: Dict[str, Any]) -> str:
        assets = sorted(
            s["decision"]["asset_scores"].items(),
            key=lambda item: item[1].get("score", 0),
            reverse=True,
        )
        lines = [
            "RANKING DE ACTIVOS",
            "ASSET                SCORE  BARRA            ACTION             TREND   MOM1M     MOM3M     VOL20D",
            "-" * 112,
        ]
        for _, m in assets:
            score = int(m.get("score", 0))
            lines.append(
                f"{(m.get('label') or '-'):<20} {score:>3}/100  {score_bar(score):<14}  "
                f"{(m.get('action') or '-'):<18}{(m.get('trend') or '-'):<8}"
                f"{signed(m.get('momentum_1m')):<10}{signed(m.get('momentum_3m')):<10}{signed(m.get('volatility_20d'))}"
            )
        return "\n".join(lines)

    def _render_assets_colored(self, s: Dict[str, Any]) -> None:
        assets = sorted(
            s["decision"]["asset_scores"].items(),
            key=lambda item: item[1].get("score", 0),
            reverse=True,
        )
        self.text.insert("end", "RANKING DE ACTIVOS\n")
        self.text.insert("end", "ASSET                SCORE  BARRA            ACTION             TREND   MOM1M     MOM3M     VOL20D\n")
        self.text.insert("end", "-" * 112 + "\n")
        for _, m in assets:
            score = int(m.get("score", 0))
            left = f"{(m.get('label') or '-'):<20} {score:>3}/100  "
            bar = f"{score_bar(score):<14}"
            right = (
                f"  {(m.get('action') or '-'):<18}{(m.get('trend') or '-'):<8}"
                f"{signed(m.get('momentum_1m')):<10}{signed(m.get('momentum_3m')):<10}{signed(m.get('volatility_20d'))}\n"
            )
            self.text.insert("end", left)
            self.text.insert("end", bar, score_tag(score))
            self.text.insert("end", right)

    def _render_news(self, s: Dict[str, Any]) -> str:
        items = s.get("news_items", [])
        lines = [
            f"NOTICIAS ({len(items)} titulares)",
            "SOURCE                    PUBLISHED               TITLE",
            "-" * 120,
        ]
        for item in items[:60]:
            lines.append(
                f"{(item.get('source') or 'RSS')[:24]:<24}"
                f"{(item.get('published_at') or '-')[:22]:<22}"
                f"{item.get('title') or '-'}"
            )
        if len(items) > 60:
            lines.append(f"... {len(items) - 60} titulares adicionales.")
        return "\n".join(lines)

    def _render_quality(self, s: Dict[str, Any]) -> str:
        q = s["data"].get("DataQuality", {})
        lines = [
            "DATA QUALITY",
            "FIELD                           STATUS    SOURCE                         DETAIL",
            "-" * 120,
        ]
        for key, meta in q.items():
            lines.append(
                f"{key[:30]:<30}{(meta.get('status') or '-'):<10}"
                f"{(meta.get('source') or '-')[:30]:<30}{(meta.get('detail') or '-')[:45]}"
            )
        return "\n".join(lines)


def main():
    _configure_windows_dpi_awareness()
    root = tk.Tk()
    NexusDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
