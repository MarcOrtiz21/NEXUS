"""
NEXUS Workstation Desktop (local app).

Interfaz local nativa (tkinter) con estilo funcional tipo terminal/Bloomberg:
- barra superior de navegación
- refresco automático cada 5 minutos
- solo redibuja si cambia la lectura
"""

from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import font as tkfont
from typing import Any, Dict

from config import CALENDAR_BLOCK_HOURS
from macos_notifications import notify_snapshot_change
from user_settings import get_setting, load_user_settings, save_user_settings
from history_view import format_history_report
from paper_trading import format_paper_report
from signal_track_record import format_track_record_report
from daily_report import export_daily_report, format_daily_report
from risk_filters.calendar import check_macro_events
from forex_engine import (
    forex_signal,
    forex_dual_perspective,
    directional_forex_semaphore,
    forex_news_bias,
    forex_bidirectional_rates,
)
from utils import (
    build_snapshot,
    snapshot_signature,
    fmt,
    signed,
    score_bar,
    metric_bar,
    to_float as _to_float,
    trend_from_metrics,
)


REFRESH_MS = 5 * 60 * 1000  # fallback; se sobreescribe con user_settings

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


def score_tag(score: int) -> str:
    if score >= 75:
        return "score_green"
    if score >= 45:
        return "score_yellow"
    return "score_red"



class NexusDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NEXUS Workstation")
        self.root.configure(bg=BG)
        self.root.geometry("1380x860")
        self.root.minsize(1100, 700)

        self._configure_tk_scaling()
        mono = self._pick_font_family(("SF Mono", "Menlo", "Cascadia Mono", "Consolas", "Courier New"))
        self.ui_font = tkfont.Font(family=mono, size=11)
        self.title_font = tkfont.Font(family=mono, size=12, weight="bold")
        self.current_snapshot: Dict[str, Any] | None = None
        self.current_signature: str | None = None
        self.current_view = "overview"
        self.fetch_in_progress = False
        self.compact_mode = False
        self.refresh_job = None

        self._build_ui()
        self.root.bind("<Command-r>", lambda _event: self._schedule_fetch(immediate=True))
        self.root.bind("<Control-r>", lambda _event: self._schedule_fetch(immediate=True))
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
            ("global", "Global"),
            ("news", "Noticias"),
            ("history", "Historial"),
            ("paper", "Paper"),
            ("track", "Track Record"),
            ("report", "Informe"),
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
        self.macro_label = tk.Label(right, text="Macro: --", fg=MUTED, bg="#070B13", font=self.ui_font)
        self.macro_label.pack(side="left", padx=6)
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

        compact_btn = tk.Button(
            footer,
            text="Modo compacto",
            command=self._toggle_compact_mode,
            fg=TEXT,
            bg=PANEL,
            activeforeground=TEXT,
            activebackground=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=4,
            font=self.ui_font,
        )
        compact_btn.pack(side="right", padx=8)

        export_btn = tk.Button(
            footer,
            text="Exportar informe",
            command=self._export_daily_report,
            fg=TEXT,
            bg=PANEL,
            activeforeground=TEXT,
            activebackground=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=4,
            font=self.ui_font,
        )
        export_btn.pack(side="right", padx=8)

        settings_btn = tk.Button(
            footer,
            text="Ajustes",
            command=self._open_settings_dialog,
            fg=TEXT,
            bg=PANEL,
            activeforeground=TEXT,
            activebackground=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=4,
            font=self.ui_font,
        )
        settings_btn.pack(side="right", padx=8)

        self._set_view("overview")
        self._update_footer_refresh_label()

    def _export_daily_report(self) -> None:
        if not self.current_snapshot:
            return
        paths = export_daily_report(self.current_snapshot)
        self.footer_left.configure(text=f"Informe exportado: {paths['html_path']}")

    def _refresh_interval_ms(self) -> int:
        return int(get_setting("refresh_interval_seconds")) * 1000

    def _update_footer_refresh_label(self) -> None:
        seconds = int(get_setting("refresh_interval_seconds"))
        self.footer_left.configure(text=f"Auto-refresh {seconds}s • Cmd+R manual • solo cambia cuando hay cambios")

    def _open_settings_dialog(self) -> None:
        settings = load_user_settings(force=True)
        dialog = tk.Toplevel(self.root)
        dialog.title("Ajustes NEXUS")
        dialog.configure(bg=PANEL)
        dialog.geometry("420x360")
        dialog.transient(self.root)
        dialog.grab_set()

        def add_row(row: int, label: str, widget) -> None:
            tk.Label(dialog, text=label, fg=MUTED, bg=PANEL, font=self.ui_font, anchor="w").grid(
                row=row, column=0, sticky="w", padx=16, pady=8
            )
            widget.grid(row=row, column=1, sticky="ew", padx=16, pady=8)

        dialog.grid_columnconfigure(1, weight=1)

        refresh_var = tk.StringVar(value=str(settings["refresh_interval_seconds"]))
        refresh_menu = tk.OptionMenu(dialog, refresh_var, "60", "120", "300", "600")
        add_row(0, "Refresco (segundos)", refresh_menu)

        block_var = tk.StringVar(value=str(settings["calendar_block_hours"]))
        block_menu = tk.OptionMenu(dialog, block_var, "3", "6")
        add_row(1, "Bloqueo calendario (h)", block_menu)

        cal_var = tk.BooleanVar(value=bool(settings["calendar_blocks_signals"]))
        add_row(2, "Bloquear por calendario", tk.Checkbutton(dialog, variable=cal_var, bg=PANEL, fg=TEXT, selectcolor=PANEL_ALT))

        sent_var = tk.BooleanVar(value=bool(settings["sentiment_blocks_signals"]))
        add_row(3, "Bloquear por sentimiento", tk.Checkbutton(dialog, variable=sent_var, bg=PANEL, fg=TEXT, selectcolor=PANEL_ALT))

        finbert_var = tk.BooleanVar(value=bool(settings["use_finbert"]))
        add_row(4, "FinBERT (opcional)", tk.Checkbutton(dialog, variable=finbert_var, bg=PANEL, fg=TEXT, selectcolor=PANEL_ALT))

        notify_var = tk.BooleanVar(value=bool(settings.get("macos_notifications", True)))
        add_row(5, "Notificaciones macOS", tk.Checkbutton(dialog, variable=notify_var, bg=PANEL, fg=TEXT, selectcolor=PANEL_ALT))

        def on_save() -> None:
            save_user_settings({
                "refresh_interval_seconds": int(refresh_var.get()),
                "calendar_block_hours": int(block_var.get()),
                "calendar_blocks_signals": cal_var.get(),
                "sentiment_blocks_signals": sent_var.get(),
                "use_finbert": finbert_var.get(),
                "macos_notifications": notify_var.get(),
            })
            self._update_footer_refresh_label()
            self._schedule_refresh_loop()
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg=PANEL)
        btn_row.grid(row=7, column=0, columnspan=2, pady=16)
        tk.Button(btn_row, text="Guardar", command=on_save, bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=6).pack(side="left", padx=8)
        tk.Button(btn_row, text="Cancelar", command=dialog.destroy, bg=PANEL, fg=MUTED, relief="flat", padx=12, pady=6).pack(side="left", padx=8)

    def _schedule_refresh_loop(self) -> None:
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
        self.refresh_job = self.root.after(self._refresh_interval_ms(), self._schedule_fetch)

    def _toggle_compact_mode(self):
        self.compact_mode = not self.compact_mode
        if self.compact_mode:
            self.root.geometry("980x620")
            self.ui_font.configure(size=10)
        else:
            self.root.geometry("1380x860")
            self.ui_font.configure(size=11)
        self._render_current()

    def _set_view(self, key: str):
        self.current_view = key
        for k, btn in self.nav_buttons.items():
            btn.configure(fg=TEXT if k == key else MUTED, bg=PANEL_ALT if k == key else PANEL)
        self.view_title.configure(text=self.nav_buttons[key]["text"])
        self._render_current()

    def _schedule_fetch(self, immediate: bool = False):
        if immediate:
            self._start_fetch()
        self._schedule_refresh_loop()

    def _start_fetch(self):
        if self.fetch_in_progress:
            return
        self.fetch_in_progress = True
        self.status_label.configure(text="Actualizando...", fg=TEXT, bg=PANEL)
        t = threading.Thread(target=self._fetch_worker, daemon=True)
        t.start()

    def _fetch_worker(self):
        try:
            raw_snap = build_snapshot(use_news=True, export=True)
            # Adaptar al formato que esperan los renderers del desktop (dicts, no objetos)
            snap = {
                "captured_at_utc": raw_snap["captured_at_utc"],
                "status": raw_snap["status_value"],
                "alerts": raw_snap["alerts"],
                "data": raw_snap["data"],
                "decision": raw_snap["decision_dict"],
                "rotation": raw_snap["rotation_dict"],
                "news_items": raw_snap["news_items"],
                "export_paths": raw_snap["export_paths"],
            }
            sig = snapshot_signature(raw_snap)
            self.root.after(0, lambda: self._on_fetch_success(snap, sig))
        except Exception as exc:
            self.root.after(0, lambda: self._on_fetch_error(exc))

    def _on_fetch_success(self, snap: Dict[str, Any], sig: str):
        changed = sig != self.current_signature
        notify_snapshot_change(self.current_snapshot, snap)
        self.fetch_in_progress = False
        self.updated_label.configure(text=snap.get("captured_at_utc", "--"))
        self.footer_right.configure(text=f"sig: {sig[:12]}")

        if changed:
            self.current_snapshot = snap
            self.current_signature = sig
            self.status_label.configure(text=f"{snap['status']} • actualizado", fg=TEXT, bg="#143726")
            self._update_macro_label(snap)
            self._render_current()
        else:
            self.status_label.configure(text=f"{snap['status']} • sin cambios", fg=TEXT, bg="#243148")
            self._update_macro_label(snap)

    def _update_macro_label(self, snap: Dict[str, Any]):
        cal = check_macro_events()
        if cal.get("should_block_signals"):
            self.macro_label.configure(
                text=f"Macro: BLOQUEO {cal.get('block_hours', CALENDAR_BLOCK_HOURS)}h",
                fg=BAD,
            )
        elif cal.get("next_event"):
            title = cal["next_event"].get("title", "Evento macro")
            self.macro_label.configure(text=f"Macro: {title[:42]}", fg=WARN)
        else:
            self.macro_label.configure(text="Macro: sin eventos inminentes", fg=GOOD)

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
            "global": self._render_global,
            "news": self._render_news,
            "history": lambda snap: format_history_report(limit=25),
            "paper": lambda snap: format_paper_report(limit=12),
            "track": lambda snap: format_track_record_report(forward_days=5, limit=100),
            "report": lambda snap: format_daily_report(snap),
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
        rates = forex_bidirectional_rates(fx)
        ranked = sorted(
            dec.get("asset_scores", {}).values(),
            key=lambda item: item.get("score", 0),
            reverse=True,
        )[:3]
        top_news = s.get("news_items", [])[:3]
        macro_action = dec.get("macro_action", dec.get("action"))
        operational_action = dec.get("operational_action", dec.get("action"))
        pause_reason = dec.get("operational_pause_reason")
        lines = [
            f"STATUS: {s['status']}    SNAPSHOT UTC: {s.get('captured_at_utc', '--')}",
            "",
            "DIAGNOSTICO MACRO",
            f"  Lectura     : {macro_action}",
            f"  Score macro : {dec['score']}/100  {score_bar(int(dec['score']), 16)}",
            "",
            "SENAL OPERATIVA",
            f"  Accion      : {operational_action}",
            f"  Confianza   : {dec['confidence']}",
            f"  Favorecidos : {', '.join(dec['favored_assets'])}",
        ]
        if pause_reason:
            lines.append(f"  Pausa       : {pause_reason}")
        lines.extend([
            "",
            "PULSO MERCADO",
            f"  VIX          {metric_bar(d.get('VIX'), 10, 40)}  {fmt(d.get('VIX'))}",
            f"  Bono 10Y     {metric_bar(d.get('US10Y'), 2, 6)}  {fmt(d.get('US10Y'), 2, '%')}",
            f"  Inflacion    {metric_bar(d.get('CPI_YoY_Pct'), 1, 6)}  {fmt(d.get('CPI_YoY_Pct'), 1, '%')}",
            f"  Liquidez M2  {metric_bar(d.get('M2_Change_Pct'), -6, 8)}  {signed(d.get('M2_Change_Pct'))}",
            f"  Curva 2Y-10Y {metric_bar(d.get('Yield_Curve_Spread'), -1, 2)}  {signed(d.get('Yield_Curve_Spread'), suffix='pp')}",
            f"  PER pct hist {metric_bar(d.get('PE_Forward_Percentile'), 0, 100)}  {fmt(d.get('PE_Forward_Percentile'), 0)}",
            f"  China M2 YoY {metric_bar(d.get('China_M2_YoY_Pct'), 2, 12)}  {fmt(d.get('China_M2_YoY_Pct'), 1, '%')}",
            f"  Correlacion  {metric_bar(abs(d.get('Correlation_Proxy')) if d.get('Correlation_Proxy') is not None else None, 0, 1)}  {fmt(d.get('Correlation_Proxy'), 3)}",
            "",
            "ROTACION",
            f"  Estado       : {rot['state']}",
            f"  Leaders 1M   : {signed(rot.get('leaders_avg_1m'))}",
            f"  Receivers 1M : {signed(rot.get('receivers_avg_1m'))}",
            "",
            "FOREX (USD / EUR)",
            f"  {rates['eur_label']}   |   {rates['usd_label']}",
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
        ])
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
        rates = forex_bidirectional_rates(fx)
        lines = [
            "FOREX DASHBOARD (USD / EUR)",
            "",
            "TIPO DE CAMBIO",
            f"  {rates['eur_label']}   |   {rates['usd_label']}",
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

    def _render_global(self, s: Dict[str, Any]) -> str:
        markets = s["data"].get("GlobalMarkets", {})
        lines = [
            "MERCADOS GLOBALES",
            "REGION     SPOT      MA20      MA50      1M        3M        TREND",
            "-" * 95,
        ]
        for region, metrics in markets.items():
            lines.append(
                f"{region:<10}{fmt(metrics.get('price'), 2):<10}{fmt(metrics.get('ma20'), 2):<10}"
                f"{fmt(metrics.get('ma50'), 2):<10}{signed(metrics.get('momentum_1m')):<10}"
                f"{signed(metrics.get('momentum_3m')):<10}{trend_from_metrics(metrics)}"
            )
        return "\n".join(lines)

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
