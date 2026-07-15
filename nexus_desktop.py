"""
NEXUS Workstation Desktop (local app).

Shell Bloomberg (denso, mono, status strip) + vistas tipadas limpias
estilo Trade Republic. Refresco automático; solo redibuja si cambia la lectura.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import font as tkfont
from typing import Any, Callable, Dict, List, Tuple

from config import CALENDAR_BLOCK_HOURS, SCORE_BUY, SCORE_HOLD
from macos_notifications import notify_snapshot_change
from user_settings import get_setting, load_user_settings, save_user_settings
from history_view import summarize_history
from paper_trading import summarize_paper_trading
from signal_track_record import track_record_chart_payload
from daily_report import export_daily_report, format_daily_report
from risk_filters.calendar import check_macro_events
from forex_engine import (
    forex_signal,
    forex_dual_perspective,
    directional_forex_semaphore,
    forex_bidirectional_rates,
)
from utils import (
    build_snapshot,
    snapshot_signature,
    fmt,
    signed,
    score_bar,
    metric_bar,
    trend_from_metrics,
)


# ─── Theme ───
BG = "#05070B"
HEADER_BG = "#070B13"
PANEL = "#0B0F17"
PANEL_ALT = "#101625"
TEXT = "#D7DEE9"
MUTED = "#8D9BB0"
LINE = "#293245"
ACCENT = "#3ED6FF"
GOOD = "#36C26A"
WARN = "#F7C948"
BAD = "#EF4F68"
CHIP_OK = "#143726"
CHIP_WARN = "#3A3218"
CHIP_BAD = "#4A1F2A"
CHIP_NEUTRAL = "#243148"

NAV_ITEMS: List[Tuple[str, str]] = [
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
]


def _configure_windows_dpi_awareness() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def score_color(score: int) -> str:
    if score >= SCORE_BUY:
        return GOOD
    if score >= SCORE_HOLD:
        return WARN
    return BAD


def status_color(status: str) -> str:
    value = (status or "").upper()
    if value in {"HEALTHY"}:
        return GOOD
    if value in {"CAUTION", "BLOCKED"}:
        return WARN
    if value in {"PANIC"}:
        return BAD
    return MUTED


class NexusDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NEXUS Workstation")
        self.root.configure(bg=BG)
        self.root.geometry("1440x900")
        self.root.minsize(1180, 720)

        self._configure_tk_scaling()
        mono = self._pick_font_family(("SF Mono", "Menlo", "Cascadia Mono", "Consolas", "Courier New"))
        sans = self._pick_font_family(("SF Pro Text", "Helvetica Neue", "Segoe UI", "Arial"))
        self.mono = mono
        self.ui_font = tkfont.Font(family=mono, size=11)
        self.small_font = tkfont.Font(family=mono, size=10)
        self.title_font = tkfont.Font(family=mono, size=12, weight="bold")
        self.brand_font = tkfont.Font(family=sans, size=18, weight="bold")
        self.section_font = tkfont.Font(family=sans, size=11, weight="bold")
        self.hero_font = tkfont.Font(family=mono, size=16, weight="bold")

        self.current_snapshot: Dict[str, Any] | None = None
        self.current_signature: str | None = None
        self.current_view = "overview"
        self.fetch_in_progress = False
        self.compact_mode = False
        self.refresh_job = None
        self._track_chart_payload: Dict[str, Any] | None = None
        self.nav_buttons: Dict[str, tk.Button] = {}
        self.nav_underlines: Dict[str, tk.Frame] = {}

        self._build_ui()
        self.root.bind("<Command-r>", lambda _event: self._schedule_fetch(immediate=True))
        self.root.bind("<Control-r>", lambda _event: self._schedule_fetch(immediate=True))
        self._schedule_fetch(immediate=True)

    # ─── Fonts / DPI ───
    def _pick_font_family(self, candidates: tuple[str, ...]) -> str:
        available = set(tkfont.families(self.root))
        for family in candidates:
            if family in available:
                return family
        return "TkFixedFont"

    def _configure_tk_scaling(self) -> None:
        try:
            pixels_per_inch = float(self.root.winfo_fpixels("1i"))
            scaling = max(1.0, pixels_per_inch / 96.0)
            self.root.tk.call("tk", "scaling", scaling)
        except Exception:
            pass

    # ─── Theme helpers ───
    def make_panel(self, parent: tk.Misc, **pack_opts) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        if pack_opts:
            frame.pack(**pack_opts)
        return frame

    def section_title(self, parent: tk.Misc, text: str) -> tk.Label:
        label = tk.Label(parent, text=text, fg=ACCENT, bg=PANEL, font=self.section_font, anchor="w")
        label.pack(fill="x", padx=14, pady=(12, 6))
        return label

    def kv_row(self, parent: tk.Misc, key: str, value: str, value_fg: str = TEXT) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=14, pady=2)
        tk.Label(row, text=key, fg=MUTED, bg=PANEL, font=self.small_font, width=16, anchor="w").pack(side="left")
        tk.Label(row, text=value, fg=value_fg, bg=PANEL, font=self.ui_font, anchor="w").pack(side="left", fill="x", expand=True)

    def metric_row(self, parent: tk.Misc, label: str, bar: str, value: str) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=14, pady=1)
        tk.Label(row, text=label, fg=MUTED, bg=PANEL, font=self.small_font, width=12, anchor="w").pack(side="left")
        tk.Label(row, text=bar, fg=ACCENT, bg=PANEL, font=self.small_font, anchor="w").pack(side="left", padx=(0, 8))
        tk.Label(row, text=value, fg=TEXT, bg=PANEL, font=self.ui_font, anchor="w").pack(side="left")

    def body_text(self, parent: tk.Misc, text: str, fg: str = TEXT, wrap: str = "word") -> tk.Label:
        label = tk.Label(parent, text=text, fg=fg, bg=PANEL, font=self.ui_font, anchor="nw", justify="left", wraplength=520)
        label.pack(fill="x", padx=14, pady=(0, 10))
        return label

    def action_button(self, parent: tk.Misc, text: str, command: Callable[[], None]) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            fg=TEXT,
            bg=PANEL_ALT,
            activeforeground=TEXT,
            activebackground=LINE,
            relief="flat",
            padx=12,
            pady=5,
            font=self.small_font,
            cursor="hand2",
            highlightthickness=0,
            bd=0,
        )
        return btn

    def _scrollable(self, parent: tk.Misc) -> Tuple[tk.Canvas, tk.Frame]:
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        def _on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def _on_mousewheel(event):
            delta = -1 if getattr(event, "delta", 0) > 0 or getattr(event, "num", None) == 4 else 1
            if sys.platform == "darwin":
                delta = -1 * int(getattr(event, "delta", 0))
            canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)
        return canvas, inner

    # ─── Shell ───
    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=HEADER_BG, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand_wrap = tk.Frame(header, bg=HEADER_BG)
        brand_wrap.pack(side="left", padx=16, pady=10)
        tk.Label(brand_wrap, text="NEXUS", fg=ACCENT, bg=HEADER_BG, font=self.brand_font).pack(anchor="w")
        tk.Label(brand_wrap, text="WORKSTATION", fg=MUTED, bg=HEADER_BG, font=self.small_font).pack(anchor="w")

        chips = tk.Frame(header, bg=HEADER_BG)
        chips.pack(side="right", padx=16)
        self.status_label = tk.Label(chips, text="Cargando…", fg=TEXT, bg=CHIP_NEUTRAL, font=self.small_font, padx=10, pady=4)
        self.status_label.pack(side="left", padx=4)
        self.macro_label = tk.Label(chips, text="Macro: —", fg=MUTED, bg=PANEL, font=self.small_font, padx=10, pady=4)
        self.macro_label.pack(side="left", padx=4)
        self.updated_label = tk.Label(chips, text="—", fg=MUTED, bg=HEADER_BG, font=self.small_font, padx=8)
        self.updated_label.pack(side="left", padx=4)

        nav_bar = tk.Frame(self.root, bg=HEADER_BG)
        nav_bar.pack(fill="x")
        nav_inner = tk.Frame(nav_bar, bg=HEADER_BG)
        nav_inner.pack(fill="x", padx=12, pady=(0, 0))
        for key, label in NAV_ITEMS:
            col = tk.Frame(nav_inner, bg=HEADER_BG)
            col.pack(side="left", padx=2)
            btn = tk.Button(
                col,
                text=label,
                command=lambda k=key: self._set_view(k),
                fg=MUTED,
                bg=HEADER_BG,
                activeforeground=TEXT,
                activebackground=HEADER_BG,
                relief="flat",
                padx=10,
                pady=8,
                font=self.small_font,
                cursor="hand2",
                highlightthickness=0,
                bd=0,
            )
            btn.pack()
            underline = tk.Frame(col, bg=HEADER_BG, height=2)
            underline.pack(fill="x")
            self.nav_buttons[key] = btn
            self.nav_underlines[key] = underline
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=BG, padx=14, pady=12)
        body.pack(fill="both", expand=True)
        self.view_title = tk.Label(body, text="Overview", fg=TEXT, bg=BG, font=self.section_font, anchor="w")
        self.view_title.pack(fill="x", pady=(0, 10))
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(fill="both", expand=True)

        footer = tk.Frame(self.root, bg=HEADER_BG)
        footer.pack(fill="x")
        tk.Frame(footer, bg=LINE, height=1).pack(fill="x")
        foot_inner = tk.Frame(footer, bg=HEADER_BG)
        foot_inner.pack(fill="x", padx=12, pady=8)
        self.footer_left = tk.Label(foot_inner, text="Auto-refresh", fg=MUTED, bg=HEADER_BG, font=self.small_font)
        self.footer_left.pack(side="left")
        self.footer_right = tk.Label(foot_inner, text="sig: —", fg=MUTED, bg=HEADER_BG, font=self.small_font)
        self.footer_right.pack(side="right", padx=(12, 0))
        for text, cmd in (
            ("Ajustes", self._open_settings_dialog),
            ("Exportar", self._export_daily_report),
            ("Compacto", self._toggle_compact_mode),
            ("Refrescar", lambda: self._schedule_fetch(immediate=True)),
        ):
            self.action_button(foot_inner, text, cmd).pack(side="right", padx=4)

        self._set_view("overview")
        self._update_footer_refresh_label()

    def _clear_content(self) -> None:
        self._track_chart_payload = None
        for child in self.content.winfo_children():
            child.destroy()
        try:
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")
        except Exception:
            pass

    # ─── Settings / refresh ───
    def _export_daily_report(self) -> None:
        if not self.current_snapshot:
            return
        paths = export_daily_report(self.current_snapshot)
        self.footer_left.configure(text=f"Informe exportado: {paths['html_path']}")

    def _refresh_interval_ms(self) -> int:
        return int(get_setting("refresh_interval_seconds")) * 1000

    def _update_footer_refresh_label(self) -> None:
        seconds = int(get_setting("refresh_interval_seconds"))
        self.footer_left.configure(text=f"Auto-refresh {seconds}s · Cmd/Ctrl+R · solo redibuja con cambios")

    def _open_settings_dialog(self) -> None:
        settings = load_user_settings(force=True)
        dialog = tk.Toplevel(self.root)
        dialog.title("Ajustes NEXUS")
        dialog.configure(bg=PANEL)
        dialog.geometry("440x380")
        dialog.transient(self.root)
        dialog.grab_set()

        def add_row(row: int, label: str, widget) -> None:
            tk.Label(dialog, text=label, fg=MUTED, bg=PANEL, font=self.ui_font, anchor="w").grid(
                row=row, column=0, sticky="w", padx=16, pady=8
            )
            widget.grid(row=row, column=1, sticky="ew", padx=16, pady=8)

        dialog.grid_columnconfigure(1, weight=1)
        refresh_var = tk.StringVar(value=str(settings["refresh_interval_seconds"]))
        add_row(0, "Refresco (segundos)", tk.OptionMenu(dialog, refresh_var, "60", "120", "300", "600"))
        block_var = tk.StringVar(value=str(settings["calendar_block_hours"]))
        add_row(1, "Bloqueo calendario (h)", tk.OptionMenu(dialog, block_var, "3", "6"))
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
        self.action_button(btn_row, "Guardar", on_save).pack(side="left", padx=8)
        self.action_button(btn_row, "Cancelar", dialog.destroy).pack(side="left", padx=8)

    def _schedule_refresh_loop(self) -> None:
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
        self.refresh_job = self.root.after(self._refresh_interval_ms(), self._schedule_fetch)

    def _toggle_compact_mode(self) -> None:
        self.compact_mode = not self.compact_mode
        if self.compact_mode:
            self.root.geometry("1040x680")
            self.ui_font.configure(size=10)
            self.small_font.configure(size=9)
        else:
            self.root.geometry("1440x900")
            self.ui_font.configure(size=11)
            self.small_font.configure(size=10)
        self._render_current()

    def _set_view(self, key: str) -> None:
        self.current_view = key
        for k, btn in self.nav_buttons.items():
            active = k == key
            btn.configure(fg=ACCENT if active else MUTED)
            self.nav_underlines[k].configure(bg=ACCENT if active else HEADER_BG)
        label = dict(NAV_ITEMS).get(key, key)
        self.view_title.configure(text=label)
        self._render_current()

    # ─── Data fetch ───
    def _schedule_fetch(self, immediate: bool = False) -> None:
        if immediate:
            self._start_fetch()
        self._schedule_refresh_loop()

    def _start_fetch(self) -> None:
        if self.fetch_in_progress:
            return
        self.fetch_in_progress = True
        self.status_label.configure(text="Actualizando…", fg=TEXT, bg=CHIP_NEUTRAL)
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        try:
            raw_snap = build_snapshot(use_news=True, export=True)
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

    def _on_fetch_success(self, snap: Dict[str, Any], sig: str) -> None:
        changed = sig != self.current_signature
        notify_snapshot_change(self.current_snapshot, snap)
        self.fetch_in_progress = False
        self.updated_label.configure(text=snap.get("captured_at_utc", "—"))
        self.footer_right.configure(text=f"sig: {sig[:12]}")
        status = snap["status"]
        if changed:
            self.current_snapshot = snap
            self.current_signature = sig
            self.status_label.configure(text=f"{status} · actualizado", fg=TEXT, bg=CHIP_OK)
            self._update_macro_label(snap)
            self._render_current()
        else:
            self.status_label.configure(text=f"{status} · sin cambios", fg=TEXT, bg=CHIP_NEUTRAL)
            self._update_macro_label(snap)

    def _update_macro_label(self, snap: Dict[str, Any]) -> None:
        cal = check_macro_events()
        if cal.get("should_block_signals"):
            self.macro_label.configure(
                text=f"Macro: BLOQUEO {cal.get('block_hours', CALENDAR_BLOCK_HOURS)}h",
                fg=BAD,
                bg=CHIP_BAD,
            )
        elif cal.get("next_event"):
            title = cal["next_event"].get("title", "Evento macro")
            self.macro_label.configure(text=f"Macro: {title[:40]}", fg=WARN, bg=CHIP_WARN)
        else:
            self.macro_label.configure(text="Macro: sin eventos", fg=GOOD, bg=CHIP_OK)

    def _on_fetch_error(self, exc: Exception) -> None:
        self.fetch_in_progress = False
        self.status_label.configure(text=f"ERROR: {exc}", fg=TEXT, bg=CHIP_BAD)

    # ─── Routing ───
    def _render_current(self) -> None:
        self._clear_content()
        if not self.current_snapshot:
            panel = self.make_panel(self.content, fill="both", expand=True)
            tk.Label(panel, text="Cargando snapshot…", fg=MUTED, bg=PANEL, font=self.ui_font).pack(padx=20, pady=40)
            return

        renderers = {
            "overview": self._view_overview,
            "rotation": self._view_rotation,
            "forex": self._view_forex,
            "assets": self._view_assets,
            "global": self._view_global,
            "news": self._view_news,
            "history": self._view_history,
            "paper": self._view_paper,
            "track": self._view_track,
            "report": self._view_report,
            "quality": self._view_quality,
        }
        renderers[self.current_view](self.current_snapshot)

    # ─── Views ───
    def _view_overview(self, s: Dict[str, Any]) -> None:
        d = s["data"]
        dec = s["decision"]
        rot = s["rotation"]
        fx = d.get("Forex", {}).get("EURUSD", {})
        uup = d.get("Assets", {}).get("UUP", {})
        fx_sig = forex_signal(fx, uup, s.get("news_items", []))
        dual = forex_dual_perspective(fx_sig)
        rates = forex_bidirectional_rates(fx)
        ranked = sorted(dec.get("asset_scores", {}).values(), key=lambda m: m.get("score", 0), reverse=True)[:3]
        macro_action = dec.get("macro_action", dec.get("action"))
        ops_action = dec.get("operational_action", dec.get("action"))
        pause = dec.get("operational_pause_reason")
        score = int(dec.get("score", 0))

        top = tk.Frame(self.content, bg=BG)
        top.pack(fill="x")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=1)

        macro = self.make_panel(top)
        macro.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.section_title(macro, "DIAGNÓSTICO MACRO")
        tk.Label(macro, text=str(macro_action), fg=TEXT, bg=PANEL, font=self.hero_font, anchor="w").pack(fill="x", padx=14)
        self.kv_row(macro, "Score", f"{score}/100  {score_bar(score, 14)}", score_color(score))
        self.kv_row(macro, "Status", str(s.get("status")), status_color(str(s.get("status"))))
        tk.Frame(macro, bg=PANEL, height=8).pack()

        ops = self.make_panel(top)
        ops.grid(row=0, column=1, sticky="nsew", padx=6)
        self.section_title(ops, "SEÑAL OPERATIVA")
        tk.Label(ops, text=str(ops_action), fg=TEXT, bg=PANEL, font=self.hero_font, anchor="w").pack(fill="x", padx=14)
        self.kv_row(ops, "Confianza", str(dec.get("confidence", "—")))
        self.kv_row(ops, "Favorecidos", ", ".join(dec.get("favored_assets") or ["—"]))
        if pause:
            self.kv_row(ops, "Pausa", str(pause), WARN)
        tk.Frame(ops, bg=PANEL, height=8).pack()

        pulse = self.make_panel(top)
        pulse.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.section_title(pulse, "PULSO MERCADO")
        for label, bar, value in (
            ("VIX", metric_bar(d.get("VIX"), 10, 40), fmt(d.get("VIX"))),
            ("Bono 10Y", metric_bar(d.get("US10Y"), 2, 6), fmt(d.get("US10Y"), 2, "%")),
            ("IPC YoY", metric_bar(d.get("CPI_YoY_Pct"), 1, 6), fmt(d.get("CPI_YoY_Pct"), 1, "%")),
            ("M2", metric_bar(d.get("M2_Change_Pct"), -6, 8), signed(d.get("M2_Change_Pct"))),
            ("Curva", metric_bar(d.get("Yield_Curve_Spread"), -1, 2), signed(d.get("Yield_Curve_Spread"), suffix="pp")),
            ("Corr", metric_bar(abs(d.get("Correlation_Proxy")) if d.get("Correlation_Proxy") is not None else None, 0, 1), fmt(d.get("Correlation_Proxy"), 3)),
        ):
            self.metric_row(pulse, label, bar, value)
        tk.Frame(pulse, bg=PANEL, height=8).pack()

        bottom = tk.Frame(self.content, bg=BG)
        bottom.pack(fill="both", expand=True, pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.columnconfigure(2, weight=1)
        bottom.columnconfigure(3, weight=1)

        rot_p = self.make_panel(bottom)
        rot_p.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.section_title(rot_p, "ROTACIÓN")
        self.kv_row(rot_p, "Estado", str(rot.get("state", "—")))
        self.kv_row(rot_p, "Leaders 1M", signed(rot.get("leaders_avg_1m")))
        self.kv_row(rot_p, "Receivers 1M", signed(rot.get("receivers_avg_1m")))
        tk.Frame(rot_p, bg=PANEL, height=8).pack()

        fx_p = self.make_panel(bottom)
        fx_p.grid(row=0, column=1, sticky="nsew", padx=6)
        self.section_title(fx_p, "FOREX")
        self.kv_row(fx_p, "Spot", rates["eur_label"])
        self.kv_row(fx_p, "Inverso", rates["usd_label"])
        self.kv_row(fx_p, "Acción", str(fx_sig.get("action", "—")))
        self.kv_row(fx_p, "EUR vista", dual.get("eur_view", "—"))
        tk.Frame(fx_p, bg=PANEL, height=8).pack()

        assets_p = self.make_panel(bottom)
        assets_p.grid(row=0, column=2, sticky="nsew", padx=6)
        self.section_title(assets_p, "TOP ACTIVOS")
        for m in ranked:
            sc = int(m.get("score", 0))
            self.kv_row(assets_p, str(m.get("label", "-"))[:14], f"{sc}/100 {score_bar(sc, 8)}", score_color(sc))
        tk.Frame(assets_p, bg=PANEL, height=8).pack()

        news_p = self.make_panel(bottom)
        news_p.grid(row=0, column=3, sticky="nsew", padx=(6, 0))
        self.section_title(news_p, "NEWS / ALERTAS")
        for alert in (s.get("alerts") or [])[:2]:
            self.body_text(news_p, f"• {alert}", MUTED)
        for item in (s.get("news_items") or [])[:2]:
            self.body_text(news_p, f"[{item.get('source', 'RSS')}] {item.get('title', '-')}", TEXT)

    def _view_rotation(self, s: Dict[str, Any]) -> None:
        r = s["rotation"]
        head = self.make_panel(self.content, fill="x", pady=(0, 10))
        self.section_title(head, "ESTADO DE ROTACIÓN")
        self.kv_row(head, "Estado", str(r.get("state", "—")))
        self.kv_row(head, "Leaders 1M", signed(r.get("leaders_avg_1m")))
        self.kv_row(head, "Receivers 1M", signed(r.get("receivers_avg_1m")))
        self.body_text(head, str(r.get("summary", "")))

        _, inner = self._scrollable(self.content)
        for t in r.get("themes", []):
            panel = self.make_panel(inner, fill="x", pady=4, padx=2)
            group = "DESCANSA" if t.get("group") == "Líderes en descanso" else "RECIBE"
            color = WARN if group == "DESCANSA" else GOOD
            self.section_title(panel, f"{group} · {t.get('theme', '')} ({t.get('ticker', '')})")
            self.kv_row(panel, "Señal", str(t.get("signal", "—")), color)
            self.kv_row(panel, "Mom 1M", signed(t.get("momentum_1m")))
            self.kv_row(panel, "vs SPY", signed(t.get("relative_1m_vs_spy")))
            self.body_text(panel, str(t.get("represents", "")), MUTED)

    def _view_forex(self, s: Dict[str, Any]) -> None:
        d = s["data"]
        fx = d.get("Forex", {}).get("EURUSD", {})
        uup = d.get("Assets", {}).get("UUP", {})
        uup_score = s["decision"].get("asset_scores", {}).get("UUP", {}).get("score")
        fx_sig = forex_signal(fx, uup, s.get("news_items", []))
        dual = forex_dual_perspective(fx_sig)
        eur_sem = directional_forex_semaphore(fx_sig.get("rel_1m") or 0.0)
        usd_sem = directional_forex_semaphore(-(fx_sig.get("rel_1m") or 0.0))
        rates = forex_bidirectional_rates(fx)

        top = tk.Frame(self.content, bg=BG)
        top.pack(fill="x")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=1)

        spot = self.make_panel(top)
        spot.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.section_title(spot, "TIPO DE CAMBIO")
        tk.Label(spot, text=rates["eur_label"], fg=TEXT, bg=PANEL, font=self.hero_font, anchor="w").pack(fill="x", padx=14)
        self.kv_row(spot, "USD/EUR", rates["usd_label"])
        self.kv_row(spot, "Acción", str(fx_sig.get("action")))
        self.kv_row(spot, "Confianza", f"{fx_sig.get('confidence')} ({fx_sig.get('score'):+d})")
        tk.Frame(spot, bg=PANEL, height=8).pack()

        eur = self.make_panel(top)
        eur.grid(row=0, column=1, sticky="nsew", padx=6)
        self.section_title(eur, "EUR/USD")
        self.kv_row(eur, "Spot", fmt(fx.get("price"), 4))
        self.kv_row(eur, "MA20/50", f"{fmt(fx.get('ma20'), 4)} / {fmt(fx.get('ma50'), 4)}")
        self.kv_row(eur, "Trend", str(fx_sig.get("eur_trend")))
        self.metric_row(eur, "Mom 1M", metric_bar(fx.get("momentum_1m"), -5, 5), signed(fx.get("momentum_1m")))
        self.metric_row(eur, "Mom 3M", metric_bar(fx.get("momentum_3m"), -10, 10), signed(fx.get("momentum_3m")))
        self.kv_row(eur, "Vista", f"{eur_sem['label']} · {dual['eur_view']}")
        tk.Frame(eur, bg=PANEL, height=8).pack()

        usd = self.make_panel(top)
        usd.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.section_title(usd, "USD (UUP)")
        self.kv_row(usd, "Spot", fmt(uup.get("price"), 2))
        self.kv_row(usd, "Trend", str(fx_sig.get("usd_trend")))
        self.metric_row(usd, "Mom 1M", metric_bar(uup.get("momentum_1m"), -5, 5), signed(uup.get("momentum_1m")))
        self.kv_row(usd, "Score", f"{uup_score if uup_score is not None else '—'}/100")
        self.kv_row(usd, "Vista", f"{usd_sem['label']} · {dual['usd_view']}")
        tk.Frame(usd, bg=PANEL, height=8).pack()

        rel = self.make_panel(self.content, fill="x", pady=(10, 0))
        self.section_title(rel, "RELATIVO EUR vs USD · NEWS")
        self.metric_row(rel, "Dif 1M", metric_bar(fx_sig.get("rel_1m"), -5, 5), signed(fx_sig.get("rel_1m"), suffix="pp"))
        self.kv_row(rel, "Evolución", f"{signed(fx_sig.get('rel_change'), suffix='pp')} → {fx_sig.get('evolution')}")
        news = fx_sig.get("news", {})
        self.kv_row(rel, "News neto", f"EUR {news.get('eur_score', 0):+d} / USD {news.get('usd_score', 0):+d} → {news.get('net_eur_minus_usd', 0):+d}")
        self.body_text(rel, str(news.get("expectation", "")))

    def _view_assets(self, s: Dict[str, Any]) -> None:
        assets = sorted(
            s["decision"].get("asset_scores", {}).items(),
            key=lambda item: item[1].get("score", 0),
            reverse=True,
        )
        _, inner = self._scrollable(self.content)
        for _, m in assets:
            score = int(m.get("score", 0))
            panel = self.make_panel(inner, fill="x", pady=4, padx=2)
            head = tk.Frame(panel, bg=PANEL)
            head.pack(fill="x", padx=14, pady=(12, 4))
            tk.Label(head, text=str(m.get("label") or "-"), fg=TEXT, bg=PANEL, font=self.hero_font).pack(side="left")
            tk.Label(head, text=f"{score}/100", fg=score_color(score), bg=PANEL, font=self.title_font).pack(side="right")
            self.kv_row(panel, "Barra", score_bar(score, 18), score_color(score))
            self.kv_row(panel, "Acción", str(m.get("action") or "—"))
            self.kv_row(panel, "Trend", str(m.get("trend") or "—"))
            self.kv_row(panel, "Mom 1M / 3M", f"{signed(m.get('momentum_1m'))}  /  {signed(m.get('momentum_3m'))}")
            self.kv_row(panel, "Vol 20d", signed(m.get("volatility_20d")))
            tk.Frame(panel, bg=PANEL, height=8).pack()

    def _view_global(self, s: Dict[str, Any]) -> None:
        markets = s["data"].get("GlobalMarkets", {}) or {}
        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True)
        cols = 2
        for idx, (region, metrics) in enumerate(markets.items()):
            r, c = divmod(idx, cols)
            panel = self.make_panel(grid)
            panel.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            grid.columnconfigure(c, weight=1)
            self.section_title(panel, region.upper())
            self.kv_row(panel, "Spot", fmt(metrics.get("price"), 2))
            self.kv_row(panel, "MA20 / MA50", f"{fmt(metrics.get('ma20'), 2)} / {fmt(metrics.get('ma50'), 2)}")
            self.kv_row(panel, "Trend", trend_from_metrics(metrics))
            self.metric_row(panel, "Mom 1M", metric_bar(metrics.get("momentum_1m"), -8, 8), signed(metrics.get("momentum_1m")))
            self.metric_row(panel, "Mom 3M", metric_bar(metrics.get("momentum_3m"), -12, 12), signed(metrics.get("momentum_3m")))
            tk.Frame(panel, bg=PANEL, height=8).pack()
        if not markets:
            panel = self.make_panel(self.content, fill="both", expand=True)
            self.body_text(panel, "Sin datos de mercados globales.")

    def _view_news(self, s: Dict[str, Any]) -> None:
        items = s.get("news_items") or []
        head = self.make_panel(self.content, fill="x", pady=(0, 8))
        self.section_title(head, f"NOTICIAS · {len(items)} titulares")
        _, inner = self._scrollable(self.content)
        for item in items[:80]:
            row = self.make_panel(inner, fill="x", pady=2, padx=2)
            meta = tk.Frame(row, bg=PANEL)
            meta.pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(meta, text=str(item.get("source") or "RSS"), fg=ACCENT, bg=PANEL, font=self.small_font).pack(side="left")
            tk.Label(meta, text=str(item.get("published_at") or "—")[:22], fg=MUTED, bg=PANEL, font=self.small_font).pack(side="right")
            self.body_text(row, str(item.get("title") or "-"))

    def _view_history(self, s: Dict[str, Any]) -> None:
        summary = summarize_history(limit=30)
        head = self.make_panel(self.content, fill="x", pady=(0, 8))
        self.section_title(head, "HISTORIAL DE DECISIONES")
        if summary["count"] == 0:
            self.body_text(head, "No hay historial todavía. Ejecuta NEXUS con exportación activa.")
            return
        self.kv_row(head, "Snapshots", str(summary["count"]))
        self.kv_row(head, "Score medio", f"{summary.get('avg_score')}  (min {summary.get('min_score')} / max {summary.get('max_score')})")

        cols = tk.Frame(self.content, bg=BG)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        left = self.make_panel(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.section_title(left, "EVOLUCIÓN RECIENTE")
        for point in summary.get("score_timeline", [])[-12:][::-1]:
            macro = point.get("macro_action") or point.get("action")
            ops = point.get("operational_action") or point.get("action")
            stamp = str(point.get("captured_at") or "")[:19]
            label = f"{macro}" if macro == ops else f"M:{macro} / O:{ops}"
            self.kv_row(left, stamp, f"score {point.get('score')} · {label}")

        right = self.make_panel(cols)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.section_title(right, "CAMBIOS DE SEÑAL")
        changes = summary.get("action_changes") or []
        if not changes:
            self.body_text(right, "Sin cambios de señal en la ventana.")
        for change in changes[-10:][::-1]:
            stamp = str(change.get("captured_at") or "")[:19]
            self.kv_row(right, stamp, f"{change.get('from')} → {change.get('to')} ({change.get('score')})")

    def _view_paper(self, s: Dict[str, Any]) -> None:
        summary = summarize_paper_trading(limit=12)
        portfolio = summary["portfolio"]
        head = tk.Frame(self.content, bg=BG)
        head.pack(fill="x")
        head.columnconfigure(0, weight=1)
        head.columnconfigure(1, weight=1)
        head.columnconfigure(2, weight=1)

        p1 = self.make_panel(head)
        p1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.section_title(p1, "PAPER VALUE")
        self.kv_row(p1, "Inicial", f"${portfolio.get('starting_value', 0):,.2f}")
        self.kv_row(p1, "Actual", f"${portfolio.get('current_value', 0):,.2f}")
        self.kv_row(p1, "Retorno", f"{summary['total_return_pct']:+.2f}%", GOOD if summary["total_return_pct"] >= 0 else BAD)

        p2 = self.make_panel(head)
        p2.grid(row=0, column=1, sticky="nsew", padx=6)
        self.section_title(p2, "BENCHMARK SPY")
        self.kv_row(p2, "Buy&Hold", f"{summary['benchmark_return_pct']:+.2f}%")
        self.kv_row(p2, "Alpha", f"{summary['alpha_vs_spy_pct']:+.2f}%", GOOD if summary["alpha_vs_spy_pct"] >= 0 else BAD)
        self.kv_row(p2, "Última acción", f"{portfolio.get('last_action')} ({portfolio.get('last_score')})")

        p3 = self.make_panel(head)
        p3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.section_title(p3, "POSICIÓN")
        holdings = portfolio.get("holdings") or {}
        if not holdings:
            self.body_text(p3, "Sin posiciones.")
        for asset, amount in sorted(holdings.items()):
            if asset == "CASH":
                self.kv_row(p3, asset, f"${amount:,.2f}")
            else:
                self.kv_row(p3, asset, f"{amount:.4f}")

        trades_p = self.make_panel(self.content, fill="both", expand=True, pady=(10, 0))
        self.section_title(trades_p, f"ÚLTIMOS TRADES ({summary['trade_count']})")
        for trade in (summary.get("trades") or [])[::-1][:12]:
            stamp = str(trade.get("captured_at") or trade.get("timestamp") or "")[:19]
            action = trade.get("action") or trade.get("side") or "—"
            detail = trade.get("detail") or trade.get("allocation") or ""
            self.kv_row(trades_p, stamp, f"{action}  {detail}")

    def _view_track(self, s: Dict[str, Any]) -> None:
        payload = track_record_chart_payload(forward_days=5, limit=100, chart_limit=40)
        self._track_chart_payload = payload

        summary = self.make_panel(self.content, fill="x", pady=(0, 8))
        self.section_title(summary, "TRACK RECORD vs SPY")
        if payload.get("sample_size", 0) == 0:
            self.body_text(summary, payload.get("message", "Sin datos de track record."))
        else:
            cols = tk.Frame(summary, bg=PANEL)
            cols.pack(fill="x", padx=8, pady=(0, 10))
            cols.columnconfigure(0, weight=1)
            cols.columnconfigure(1, weight=1)
            left = tk.Frame(cols, bg=PANEL)
            left.grid(row=0, column=0, sticky="nsew")
            right = tk.Frame(cols, bg=PANEL)
            right.grid(row=0, column=1, sticky="nsew")
            self.kv_row(left, "Muestras", str(payload.get("sample_size")))
            self.kv_row(left, "Forward", f"{payload.get('forward_days')} días")
            self.kv_row(left, "Macro buys", str(payload.get("macro_buy_count")))
            hit_m = payload.get("macro_buy_hit_rate_pct")
            self.kv_row(left, "Acierto macro", f"{hit_m:.0f}%" if hit_m is not None else "—", GOOD)
            self.kv_row(right, "Defensivas", str(payload.get("defensive_count")))
            hit_d = payload.get("defensive_hit_rate_pct")
            self.kv_row(right, "Acierto ops", f"{hit_d:.0f}%" if hit_d is not None else "—", WARN)
            avg = payload.get("macro_buy_avg_return_pct")
            self.kv_row(right, "Retorno medio buy", f"{avg:+.2f}%" if avg is not None else "—")

        chart_frame = self.make_panel(self.content, fill="x", pady=(0, 8))
        canvas = tk.Canvas(chart_frame, bg=PANEL, highlightthickness=0, height=230)
        canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.track_canvas = canvas
        canvas.bind("<Configure>", lambda _e: self._redraw_track_chart_if_visible())
        self._draw_track_chart(payload)

        recent = self.make_panel(self.content, fill="both", expand=True)
        self.section_title(recent, "ÚLTIMAS MUESTRAS")
        for sample in (payload.get("recent_samples") or [])[::-1]:
            stamp = str(sample.get("captured_at") or "")[:19]
            ret = sample.get("spy_forward_return_pct")
            ret_s = f"{ret:+.2f}%" if ret is not None else "—"
            self.kv_row(
                recent,
                stamp,
                f"M:{sample.get('macro_action')}  O:{sample.get('operational_action')}  SPY {ret_s}",
                GOOD if (ret or 0) >= 0 else BAD,
            )

    def _redraw_track_chart_if_visible(self) -> None:
        if self.current_view == "track" and self._track_chart_payload is not None and hasattr(self, "track_canvas"):
            self._draw_track_chart(self._track_chart_payload)

    def _draw_track_chart(self, payload: Dict[str, Any]) -> None:
        canvas = self.track_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 640)
        height = max(canvas.winfo_height(), 220)
        pad = 16

        if payload.get("sample_size", 0) == 0:
            canvas.create_text(width // 2, height // 2, text=payload.get("message", "Sin datos"), fill=MUTED, font=self.ui_font)
            return

        left_w = int(width * 0.28)
        canvas.create_text(pad, pad, text="ACIERTO %", anchor="nw", fill=ACCENT, font=self.title_font)
        bar_top = pad + 28
        bar_h = 22
        bar_gap = 36
        max_bar_w = left_w - pad * 2 - 70
        for idx, item in enumerate(payload.get("hit_bars", [])):
            y = bar_top + idx * bar_gap
            value = item.get("value")
            color = GOOD if item.get("color") == "good" else WARN
            label = f"{item.get('label')} (n={item.get('count', 0)})"
            canvas.create_text(pad, y, text=label, anchor="nw", fill=MUTED, font=self.ui_font)
            canvas.create_rectangle(pad, y + 16, pad + max_bar_w, y + 16 + bar_h, outline=LINE, fill=PANEL_ALT)
            if value is not None:
                fill_w = max(2, int(max_bar_w * max(0.0, min(100.0, float(value))) / 100.0))
                canvas.create_rectangle(pad, y + 16, pad + fill_w, y + 16 + bar_h, outline="", fill=color)
                canvas.create_text(pad + max_bar_w + 8, y + 16 + bar_h // 2, text=f"{value:.0f}%", anchor="w", fill=TEXT, font=self.ui_font)
            else:
                canvas.create_text(pad + max_bar_w + 8, y + 16 + bar_h // 2, text="—", anchor="w", fill=MUTED, font=self.ui_font)

        right_x0 = left_w + 8
        right_x1 = width - pad
        chart_top = pad + 24
        chart_bottom = height - pad - 18
        zero_y = (chart_top + chart_bottom) / 2
        samples = payload.get("chart_samples") or []
        canvas.create_text(
            right_x0, pad,
            text=f"SPY forward {payload.get('forward_days', 5)}d  (últimas {len(samples)})",
            anchor="nw", fill=ACCENT, font=self.title_font,
        )
        canvas.create_line(right_x0, chart_top, right_x0, chart_bottom, fill=LINE)
        canvas.create_line(right_x0, chart_bottom, right_x1, chart_bottom, fill=LINE)
        canvas.create_line(right_x0, zero_y, right_x1, zero_y, fill="#3A4660", dash=(3, 3))
        canvas.create_text(right_x0 - 4, zero_y, text="0%", anchor="e", fill=MUTED, font=self.ui_font)

        if not samples:
            canvas.create_text((right_x0 + right_x1) / 2, (chart_top + chart_bottom) / 2, text="Sin series", fill=MUTED, font=self.ui_font)
            return

        returns = [float(s.get("spy_forward_return_pct") or 0.0) for s in samples]
        max_abs = max(1.0, max(abs(v) for v in returns))
        usable_w = max(40, right_x1 - right_x0 - 10)
        gap = 2
        bar_w = max(3, int((usable_w - gap * len(samples)) / max(1, len(samples))))
        half_h = (chart_bottom - chart_top) / 2 - 4
        for idx, sample in enumerate(samples):
            value = float(sample.get("spy_forward_return_pct") or 0.0)
            x0 = right_x0 + 6 + idx * (bar_w + gap)
            x1 = x0 + bar_w
            h = (abs(value) / max_abs) * half_h
            if value >= 0:
                y0, y1, fill = zero_y - h, zero_y, GOOD
            else:
                y0, y1, fill = zero_y, zero_y + h, BAD
            action = sample.get("macro_action") or ""
            outline = ACCENT if action in {"COMPRAR", "COMPRAR PARCIAL"} else LINE
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline)
        canvas.create_text(
            right_x1, height - pad + 2,
            text="verde=+ / rojo=− · borde cian=macro COMPRAR",
            anchor="se", fill=MUTED, font=self.ui_font,
        )

    def _view_report(self, s: Dict[str, Any]) -> None:
        panel = self.make_panel(self.content, fill="both", expand=True)
        self.section_title(panel, "INFORME DIARIO")
        text = tk.Text(
            panel,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=CHIP_NEUTRAL,
            relief="flat",
            wrap="word",
            font=self.ui_font,
            padx=12,
            pady=8,
            highlightthickness=0,
        )
        text.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        text.insert("1.0", format_daily_report(s))
        text.configure(state="disabled")

    def _view_quality(self, s: Dict[str, Any]) -> None:
        q = s["data"].get("DataQuality", {}) or {}
        _, inner = self._scrollable(self.content)
        if not q:
            panel = self.make_panel(inner, fill="x")
            self.body_text(panel, "Sin metadatos de calidad.")
            return
        for key, meta in q.items():
            status = str(meta.get("status") or "-")
            color = GOOD if status == "OK" else (WARN if status == "STALE" else BAD)
            panel = self.make_panel(inner, fill="x", pady=3, padx=2)
            head = tk.Frame(panel, bg=PANEL)
            head.pack(fill="x", padx=14, pady=(10, 2))
            tk.Label(head, text=key, fg=TEXT, bg=PANEL, font=self.title_font).pack(side="left")
            tk.Label(head, text=status, fg=color, bg=PANEL, font=self.small_font).pack(side="right")
            self.kv_row(panel, "Source", str(meta.get("source") or "—"))
            detail = meta.get("detail") or ""
            if detail:
                self.body_text(panel, str(detail), MUTED)
            else:
                tk.Frame(panel, bg=PANEL, height=8).pack()


def main():
    _configure_windows_dpi_awareness()
    root = tk.Tk()
    NexusDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
