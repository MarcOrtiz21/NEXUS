"""
NEXUS Workstation Desktop (local app).

UI estilo macOS (sidebar + cards redondeadas), colores Apple HIG dark.
Prioriza información: sin logo en panel, overview orientado a decisión.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import customtkinter as ctk

from config import CALENDAR_BLOCK_HOURS, SCORE_BUY, SCORE_HOLD
from macos_notifications import notify_snapshot_change
from macos_vibrancy import GlassScrollHost
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
    trend_from_metrics,
)


# Shell opaco estilo Apple HIG dark. (Blur real no es viable con CustomTkinter/Tk.)
CARD = "#2C2C30"
CARD_INNER = "#1C1C1F"
CHROME_BG = "#141416"
TEXT = "#FFFFFF"
MUTED = "#98989D"
LINE = "#3A3A3E"
ACCENT = "#0A84FF"
NAV_ACTIVE = "#3A4558"
NAV_ACTIVE_HOVER = "#455468"
NAV_IDLE = "#141416"
SOLID_CHIP = "#1C1C1F"
GOOD = "#30D158"
WARN = "#FF9F0A"
BAD = "#FF453A"
CHIP_OK = "#0F2A18"
CHIP_WARN = "#2A1F0A"
CHIP_BAD = "#2A1010"
CHIP_NEUTRAL = "#3A3A3C"
BTN_FG = "#FFFFFF"
BTN_BG = "#3A3A3C"
BTN_HOVER = "#48484A"
BAR_HEIGHT = 4

# key, label, icon glyph
NAV_ITEMS: List[Tuple[str, str, str]] = [
    ("overview", "Overview", "◉"),
    ("rotation", "Rotación", "⟳"),
    ("forex", "Forex", "⇄"),
    ("assets", "Activos", "▣"),
    ("global", "Global", "◎"),
    ("news", "Noticias", "☰"),
    ("history", "Historial", "◷"),
    ("paper", "Paper", "◈"),
    ("track", "Track Record", "▤"),
    ("report", "Informe", "▦"),
    ("quality", "Data Quality", "✓"),
]

NAV_LABELS = {k: label for k, label, _ in NAV_ITEMS}
CORNER = 14
INNER_CORNER = 10


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
    if value == "HEALTHY":
        return GOOD
    if value in {"CAUTION", "BLOCKED"}:
        return WARN
    if value == "PANIC":
        return BAD
    return MUTED


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _norm(value: float | None, low: float, high: float) -> float:
    if value is None or high == low:
        return 0.0
    return _clamp01((float(value) - low) / (high - low))


def _relative_age(ts: float | None) -> str:
    if ts is None:
        return "sin datos"
    seconds = max(0, int(time.time() - ts))
    if seconds < 5:
        return "ahora"
    if seconds < 60:
        return f"hace {seconds}s"
    if seconds < 3600:
        return f"hace {seconds // 60}m"
    return f"hace {seconds // 3600}h"


def rotation_trade_action(theme: Dict[str, Any]) -> Tuple[str, str]:
    """Mapa señal de rotación → COMPRAR / ESPERAR / VENDER + color."""
    signal = str(theme.get("signal") or "")
    if signal in {"Entrada clara de flujo", "Liderazgo aún fuerte"}:
        return "COMPRAR", GOOD
    if signal in {"Corrección activa", "Descanso sano tras liderazgo"}:
        return "VENDER", BAD
    if signal in {"Mejora incipiente"}:
        return "COMPRAR", WARN
    return "ESPERAR", MUTED


class NexusDesktopApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        settings = load_user_settings(force=True)
        self.title("NEXUS Workstation")
        self.geometry(str(settings.get("window_geometry") or "1440x900"))
        self.minsize(980, 640)
        self.configure(fg_color=CHROME_BG)

        self.current_snapshot: Dict[str, Any] | None = None
        self.current_signature: str | None = None
        self.current_view = str(settings.get("last_view") or "overview")
        self.fetch_in_progress = False
        self.compact_mode = bool(settings.get("compact_mode"))
        self.auto_refresh_enabled = True
        self.refresh_job = None
        self._next_refresh_at: float | None = None
        self._track_chart_payload: Dict[str, Any] | None = None
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.last_success_at: float | None = None
        self.last_error: str | None = None
        self._toast_job = None
        self._persist_job = None
        self._wrap_job = None
        self._render_gen = 0
        self._wrap_labels: List[Any] = []
        self._content_slot: tk.Frame | None = None
        self._scroll_host: GlassScrollHost | None = None
        self._head_right: tk.Frame | None = None
        self._chips_host: tk.Frame | None = None
        self._macro_state: Tuple[str, str, str] = ("Macro: —", MUTED, CHIP_NEUTRAL)
        self._status_state: Tuple[str, str, str] = ("…", TEXT, CHIP_NEUTRAL)
        self._view_job = None
        self._alive = True
        self._switching = False
        self._pending_render = False

        if self.compact_mode:
            self.geometry("1040x700")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Command-r>", lambda _e: self._schedule_fetch(immediate=True))
        self.bind("<Control-r>", lambda _e: self._schedule_fetch(immediate=True))
        self.bind("<Up>", lambda _e: self._nav_step(-1))
        self.bind("<Down>", lambda _e: self._nav_step(1))
        for idx in range(1, 10):
            self.bind(str(idx), lambda _e, i=idx: self._nav_by_index(i - 1))
            self.bind(f"<KP_{idx}>", lambda _e, i=idx: self._nav_by_index(i - 1))
        self.bind("<Configure>", self._on_configure)
        self.after(80, self._bring_to_front)
        self.after(1000, self._tick_status)
        self._schedule_fetch(immediate=True)

    def _safe_after(self, delay_ms: int, fn: Callable[[], None]) -> None:
        """after() que no crashea si la ventana/vista ya no existe."""
        gen = self._render_gen

        def runner() -> None:
            if not self._alive:
                return
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            if gen != self._render_gen:
                return
            try:
                fn()
            except Exception:
                pass

        self.after(delay_ms, runner)

    def _bring_to_front(self) -> None:
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(350, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass
        if sys.platform == "darwin":
            try:
                import os
                import subprocess

                pid = os.getpid()
                subprocess.Popen(
                    [
                        "osascript",
                        "-e",
                        f'tell application "System Events" to set frontmost of first process whose unix id is {pid} to true',
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    # ─── UI helpers ───
    def make_card(self, parent: Any, **pack) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            corner_radius=CORNER,
            border_width=0,
            bg_color=CHROME_BG,
        )
        if pack:
            card.pack(**pack)
        return card

    def make_row(self, parent: Any, **pack) -> tk.Frame:
        """Fila tipo mini-recuadro con tk (estable al resize; sin CTk place)."""
        row = tk.Frame(parent, bg=CARD_INNER, highlightthickness=0, bd=0)
        if pack:
            row.pack(**pack)
        return row

    def layout(self, parent: Any | None = None, **pack) -> tk.Frame:
        """Contenedor de layout ligero."""
        frame = tk.Frame(parent or self.content, bg=CHROME_BG, highlightthickness=0, bd=0)
        if pack:
            frame.pack(**pack)
        return frame

    def _grid_cols(self, preferred: int = 2) -> int:
        try:
            width = int(self.winfo_width())
        except Exception:
            width = 1100
        if width < 50:
            width = 1100
        if width < 900:
            return 1
        if width < 1200:
            return min(2, preferred)
        return preferred

    def wire_click(self, widget: Any, command: Callable[[], None]) -> None:
        def handler(_event=None) -> None:
            if self._alive:
                command()

        try:
            widget.bind("<Button-1>", handler)
        except Exception:
            return
        try:
            widget.configure(cursor="hand2")
        except Exception:
            pass
        try:
            children = widget.winfo_children()
        except Exception:
            return
        for child in children:
            self.wire_click(child, command)

    def section_title(self, parent: Any, text: str, hint: str | None = None) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color=CARD, bg_color=CARD)
        row.pack(fill="x", padx=14, pady=(12, 6))
        label = ctk.CTkLabel(
            row,
            text=text,
            text_color=ACCENT,
            fg_color=CARD,
            font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"),
            anchor="w",
        )
        label.pack(side="left")
        if hint:
            ctk.CTkLabel(
                row, text=hint, text_color=MUTED, fg_color=CARD, font=ctk.CTkFont(size=11), anchor="e"
            ).pack(side="right")
        return label

    def kv_row(self, parent: Any, key: str, value: str, value_color: str = TEXT) -> None:
        row = ctk.CTkFrame(parent, fg_color=CARD, bg_color=CARD)
        row.pack(fill="x", padx=14, pady=1)
        ctk.CTkLabel(
            row, text=key, text_color=MUTED, fg_color=CARD, font=ctk.CTkFont(size=12), width=100, anchor="w"
        ).pack(side="left")
        ctk.CTkLabel(
            row,
            text=value,
            text_color=value_color,
            fg_color=CARD,
            font=ctk.CTkFont(family="Menlo", size=12),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def progress_row(
        self,
        parent: Any,
        label: str,
        ratio: float,
        value: str,
        color: str = ACCENT,
        label_width: int = 78,
    ) -> None:
        row = ctk.CTkFrame(parent, fg_color=CARD, bg_color=CARD)
        row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(row, text=label, text_color=MUTED, font=ctk.CTkFont(size=12), width=label_width, anchor="w").pack(
            side="left"
        )
        bar = ctk.CTkProgressBar(
            row,
            height=BAR_HEIGHT,
            corner_radius=2,
            progress_color=color,
            fg_color=CARD_INNER,
        )
        bar.pack(side="left", fill="x", expand=True, padx=(6, 8))
        bar.set(_clamp01(ratio))
        ctk.CTkLabel(row, text=value, text_color=TEXT, font=ctk.CTkFont(family="Menlo", size=11), width=72, anchor="e").pack(
            side="right"
        )

    def metric_progress(self, parent: Any, label: str, value: float | None, low: float, high: float, display: str) -> None:
        ratio = _norm(value, low, high)
        if value is None:
            color = MUTED
        elif ratio >= 0.75:
            color = BAD if label in {"VIX", "IPC YoY", "Corr"} else GOOD
        elif ratio >= 0.45:
            color = WARN
        else:
            color = GOOD if label in {"VIX", "IPC YoY", "Corr"} else ACCENT
        self.progress_row(parent, label, ratio, display, color=color)

    def body_text(self, parent: Any, text: str, color: str = TEXT, wrap: int | None = None) -> None:
        wraplength = wrap if wrap is not None else self._content_wrap()
        # Fondo sólido del padre card → sin fantasmas al cambiar de vista
        label = ctk.CTkLabel(
            parent,
            text=text,
            text_color=color,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
            wraplength=wraplength,
            fg_color=CARD,
        )
        label.pack(fill="x", padx=14, pady=(0, 8))
        self._wrap_labels.append(label)

    def _content_wrap(self) -> int:
        try:
            width = int(self.winfo_width())
        except Exception:
            width = 1100
        return max(240, width - 220)

    def _refresh_wraplengths(self) -> None:
        wrap = self._content_wrap()
        alive: List[Any] = []
        for label in self._wrap_labels:
            try:
                if label.winfo_exists():
                    label.configure(wraplength=wrap)
                    alive.append(label)
            except Exception:
                pass
        self._wrap_labels = alive

    def _arm_content_scroll(self) -> None:
        """Trackpad sobre el contenido (GlassScrollHost o CTkScrollableFrame)."""
        if self._scroll_host is not None:
            try:
                self._scroll_host.arm_wheel_tree()
            except Exception:
                pass
            return
        try:
            canvas = self.content._parent_canvas  # type: ignore[attr-defined]
        except Exception:
            return

        def on_wheel(event: Any) -> str:
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass
            delta = getattr(event, "delta", 0) or 0
            if sys.platform == "darwin":
                steps = int(-delta)
            else:
                steps = int(-delta / 120) if delta else 0
            if steps == 0 and getattr(event, "num", None) in (4, 5):
                steps = -3 if event.num == 4 else 3
            if steps:
                canvas.yview_scroll(steps, "units")
            return "break"

        def bind_tree(widget: Any) -> None:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    widget.bind(seq, on_wheel, add="+")
                except Exception:
                    pass
            try:
                children = widget.winfo_children()
            except Exception:
                return
            for child in children:
                bind_tree(child)

        try:
            canvas.bind("<MouseWheel>", on_wheel, add="+")
            bind_tree(self.content)
        except Exception:
            pass

    def action_button(self, parent: Any, text: str, command: Callable[[], None], primary: bool = False, width: int = 96) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=30,
            corner_radius=9,
            fg_color=ACCENT if primary else BTN_BG,
            bg_color=CHROME_BG,
            hover_color="#0060DF" if primary else BTN_HOVER,
            text_color=BTN_FG,
            font=ctk.CTkFont(size=12, weight="bold"),
        )

    def show_toast(self, message: str, ok: bool = True) -> None:
        if hasattr(self, "_toast") and self._toast.winfo_exists():
            self._toast.destroy()
        self._toast = ctk.CTkFrame(self, fg_color=CHIP_OK if ok else CHIP_BAD, corner_radius=10)
        self._toast.place(relx=0.5, rely=0.94, anchor="center")
        ctk.CTkLabel(
            self._toast,
            text=message,
            text_color=GOOD if ok else BAD,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(padx=16, pady=8)
        if self._toast_job is not None:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(2600, self._toast.destroy)

    # ─── Shell ───
    def _build_ui(self) -> None:
        try:
            self.configure(fg_color=CHROME_BG)
            tk.Tk.configure(self, bg=CHROME_BG)
        except Exception:
            pass

        root = tk.Frame(self, bg=CHROME_BG, highlightthickness=0, bd=0)
        root.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(root, bg=CHROME_BG, width=176, highlightthickness=0, bd=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=CHROME_BG)
        brand.pack(fill="x", padx=12, pady=(14, 8))
        ctk.CTkLabel(
            brand,
            text="NEXUS",
            text_color=TEXT,
            fg_color=CHROME_BG,
            font=ctk.CTkFont(family="SF Pro Display", size=15, weight="bold"),
            anchor="w",
        ).pack(fill="x")

        nav_wrap = tk.Frame(self.sidebar, bg=CHROME_BG)
        nav_wrap.pack(fill="both", expand=True, padx=6, pady=2)
        for key, label, icon in NAV_ITEMS:
            btn = ctk.CTkButton(
                nav_wrap,
                text=f"  {icon}  {label}",
                anchor="w",
                height=30,
                corner_radius=8,
                fg_color=NAV_IDLE,
                bg_color=CHROME_BG,
                hover_color=CARD,
                text_color=MUTED,
                font=ctk.CTkFont(size=12),
                command=lambda k=key: self._set_view(k),
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[key] = btn

        self.sidebar_status = ctk.CTkLabel(
            self.sidebar,
            text="Cargando…",
            text_color=MUTED,
            fg_color=SOLID_CHIP,
            corner_radius=8,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.sidebar_status.pack(fill="x", padx=12, pady=(4, 12))

        main = tk.Frame(root, bg=CHROME_BG, highlightthickness=0, bd=0)
        main.pack(side="left", fill="both", expand=True)

        footer = tk.Frame(main, bg=CHROME_BG, highlightthickness=0, bd=0)
        footer.pack(side="bottom", fill="x", padx=12, pady=6)
        self.footer_left = ctk.CTkLabel(
            footer,
            text="Auto-refresh",
            text_color=MUTED,
            fg_color=SOLID_CHIP,
            corner_radius=8,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.footer_left.pack(side="left")
        self.action_button(footer, "Ajustes", self._open_settings_dialog, width=80).pack(side="right", padx=3)
        self.action_button(footer, "Exportar", self._export_daily_report, width=80).pack(side="right", padx=3)

        header = tk.Frame(main, bg=CHROME_BG, highlightthickness=0, bd=0)
        header.pack(fill="x", padx=14, pady=(10, 4))
        self._head_left = tk.Frame(header, bg=CHROME_BG)
        self._head_left.pack(side="left", fill="y")
        self.view_title = None
        self.view_subtitle = None
        self._paint_header_labels("overview")

        self._head_right = tk.Frame(header, bg=CHROME_BG)
        self._head_right.pack(side="right")
        self._chips_host = tk.Frame(self._head_right, bg=CHROME_BG)
        self._chips_host.pack(side="left")
        self.macro_chip = None
        self.status_chip = None
        self._paint_status_chips()

        self.auto_chip = ctk.CTkButton(
            self._head_right,
            text="Auto",
            width=56,
            height=28,
            corner_radius=8,
            fg_color=CHIP_OK,
            hover_color="#163820",
            text_color=GOOD,
            bg_color=CHROME_BG,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_auto_refresh,
        )
        self.auto_chip.pack(side="left", padx=(8, 4))
        self.action_button(
            self._head_right, "↻", lambda: self._schedule_fetch(immediate=True), primary=True, width=36
        ).pack(side="left")

        self._content_slot = tk.Frame(main, bg=CHROME_BG, highlightthickness=0, bd=0)
        self._content_slot.pack(fill="both", expand=True, padx=12, pady=(0, 2))
        self._mount_content_host()

        self._apply_view(self.current_view)
        self._update_footer_status()

    def _paint_header_labels(self, key: str) -> None:
        """Recrea título/subtítulo (única forma fiable de no dejar texto fantasma)."""
        subtitles = {
            "overview": "Qué hacer ahora y por qué",
            "rotation": "Líderes y receptores de flujo",
            "forex": "EUR/USD y sesgo relativo",
            "assets": "Ranking y momentum por activo",
            "global": "Proxies regionales",
            "news": "Flujo de titulares",
            "history": "Evolución de señales",
            "paper": "Cartera virtual vs SPY",
            "track": "Acierto retrospectivo vs SPY",
            "report": "Informe diario exportable",
            "quality": "Estado de fuentes de datos",
        }
        for child in list(self._head_left.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self.view_title = ctk.CTkLabel(
            self._head_left,
            text=NAV_LABELS.get(key, key),
            text_color=TEXT,
            fg_color=CHROME_BG,
            font=ctk.CTkFont(family="SF Pro Display", size=22, weight="bold"),
            anchor="w",
        )
        self.view_title.pack(anchor="w")
        self.view_subtitle = ctk.CTkLabel(
            self._head_left,
            text=subtitles.get(key, ""),
            text_color=MUTED,
            fg_color=CHROME_BG,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.view_subtitle.pack(anchor="w")

    def _paint_status_chips(self) -> None:
        """Recrea chips de macro/status para evitar solapes y fantasmas de CTk."""
        if self._chips_host is None:
            return
        for child in list(self._chips_host.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        macro_text, macro_fg, macro_bg = self._macro_state
        status_text, status_fg, status_bg = self._status_state
        self.macro_chip = ctk.CTkLabel(
            self._chips_host,
            text=macro_text,
            text_color=macro_fg,
            fg_color=macro_bg,
            corner_radius=8,
            padx=10,
            pady=5,
            font=ctk.CTkFont(size=11),
        )
        self.macro_chip.pack(side="left", padx=(0, 6))
        self.status_chip = ctk.CTkLabel(
            self._chips_host,
            text=status_text,
            text_color=status_fg,
            fg_color=status_bg,
            corner_radius=8,
            padx=10,
            pady=5,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.status_chip.pack(side="left")

    def _set_macro_chip(self, text: str, color: str, bg: str) -> None:
        self._macro_state = (text, color, bg)
        self._paint_status_chips()

    def _set_status_chip(self, text: str, color: str, bg: str) -> None:
        self._status_state = (text, color, bg)
        self._paint_status_chips()

    def _set_header_chips(
        self,
        *,
        status_text: str | None = None,
        status_color: str | None = None,
        status_bg: str | None = None,
        macro_text: str | None = None,
        macro_color: str | None = None,
        macro_bg: str | None = None,
    ) -> None:
        if status_text is not None and status_color is not None and status_bg is not None:
            self._status_state = (status_text, status_color, status_bg)
        if macro_text is not None and macro_color is not None and macro_bg is not None:
            self._macro_state = (macro_text, macro_color, macro_bg)
        self._paint_status_chips()

    def _mount_content_host(self) -> None:
        """Área scroll estable (tk) + cards CTk opacas."""
        if self._content_slot is None:
            return
        for child in list(self._content_slot.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self._wrap_labels = []
        self._track_chart_payload = None
        self._scroll_host = GlassScrollHost(self._content_slot)
        # Fondo sólido del scroll (sin blur; evita canvas CTk negros)
        try:
            self._scroll_host.outer.configure(bg=CHROME_BG)
            self._scroll_host.canvas.configure(bg=CHROME_BG)
            self._scroll_host.inner.configure(bg=CHROME_BG)
        except Exception:
            pass
        self._scroll_host.pack(fill="both", expand=True)
        self.content = self._scroll_host.inner
        try:
            self.update_idletasks()
        except Exception:
            pass

    # ─── Settings / persistence ───
    def _export_daily_report(self) -> None:
        if not self.current_snapshot:
            self.show_toast("Sin snapshot para exportar", ok=False)
            return
        paths = export_daily_report(self.current_snapshot)
        name = Path(paths["html_path"]).name
        self.show_toast(f"Informe guardado · {name}")

    def _refresh_interval_ms(self) -> int:
        return int(get_setting("refresh_interval_seconds")) * 1000

    def _update_footer_status(self) -> None:
        seconds = int(get_setting("refresh_interval_seconds"))
        age = _relative_age(self.last_success_at)
        if not self.auto_refresh_enabled:
            next_txt = "auto OFF"
            if hasattr(self, "auto_chip"):
                self.auto_chip.configure(text="Off", fg_color=CHIP_NEUTRAL, text_color=MUTED)
        else:
            if hasattr(self, "auto_chip"):
                self.auto_chip.configure(text="Auto", fg_color=CHIP_OK, text_color=GOOD)
            if self._next_refresh_at is None:
                next_txt = f"auto {seconds}s"
            else:
                remain = max(0, int(self._next_refresh_at - time.time()))
                next_txt = f"próx. {remain}s" if remain < 120 else f"próx. {remain // 60}m"
        try:
            self.footer_left.configure(
                text=f"Actualizado {age} · {next_txt} · ↑↓ · Cmd+R",
                fg_color=SOLID_CHIP,
            )
        except Exception:
            pass

    def _tick_status(self) -> None:
        self._update_footer_status()
        self.after(1000, self._tick_status)

    def _toggle_auto_refresh(self) -> None:
        self.auto_refresh_enabled = not self.auto_refresh_enabled
        if self.auto_refresh_enabled:
            self._schedule_refresh_loop()
            self.show_toast(f"Auto-refresh ON · cada {get_setting('refresh_interval_seconds')}s")
        else:
            if self.refresh_job is not None:
                self.after_cancel(self.refresh_job)
                self.refresh_job = None
            self._next_refresh_at = None
            self.show_toast("Auto-refresh OFF", ok=False)
        self._update_footer_status()

    def _persist_ui_state(self) -> None:
        save_user_settings({
            "last_view": self.current_view,
            "window_geometry": self.geometry().split("+")[0],
            "compact_mode": self.compact_mode,
        })

    def _schedule_persist(self) -> None:
        if self._persist_job is not None:
            self.after_cancel(self._persist_job)
        # Debounce largo: no tocar disco/UI en cada pixel del resize
        self._persist_job = self.after(900, self._persist_ui_state)

    def _schedule_wrap_refresh(self) -> None:
        if self._wrap_job is not None:
            self.after_cancel(self._wrap_job)
        self._wrap_job = self.after(250, self._refresh_wraplengths)

    def _on_configure(self, event=None) -> None:
        # Ignorar Configure de widgets hijos (solo ventana)
        if event is not None and event.widget is not self:
            return
        self._schedule_persist()
        self._schedule_wrap_refresh()

    def _on_close(self) -> None:
        self._alive = False
        self._render_gen += 1
        try:
            self._persist_ui_state()
        except Exception:
            pass
        self.destroy()

    def _set_status_text(self, text: str, color: str = MUTED) -> None:
        try:
            self.sidebar_status.configure(text=text, text_color=color, fg_color=SOLID_CHIP)
        except Exception:
            pass

    def _open_settings_dialog(self) -> None:
        settings = load_user_settings(force=True)
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ajustes NEXUS")
        dialog.geometry("440x460")
        dialog.configure(fg_color=CARD_INNER)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Ajustes", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(16, 10))

        refresh_var = ctk.StringVar(value=str(settings["refresh_interval_seconds"]))
        block_var = ctk.StringVar(value=str(settings["calendar_block_hours"]))
        cal_var = ctk.BooleanVar(value=bool(settings["calendar_blocks_signals"]))
        sent_var = ctk.BooleanVar(value=bool(settings["sentiment_blocks_signals"]))
        finbert_var = ctk.BooleanVar(value=bool(settings["use_finbert"]))
        notify_var = ctk.BooleanVar(value=bool(settings.get("macos_notifications", True)))
        compact_var = ctk.BooleanVar(value=bool(self.compact_mode))

        def add_menu(label: str, var: ctk.StringVar, values: List[str]) -> None:
            row = ctk.CTkFrame(dialog, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(row, text=label, text_color=MUTED, width=180, anchor="w").pack(side="left")
            ctk.CTkOptionMenu(row, variable=var, values=values, width=140).pack(side="right")

        def add_check(label: str, var: ctk.BooleanVar) -> None:
            ctk.CTkCheckBox(dialog, text=label, variable=var, text_color=TEXT).pack(anchor="w", padx=20, pady=5)

        add_menu("Refresco (segundos)", refresh_var, ["60", "120", "300", "600"])
        add_menu("Bloqueo calendario (h)", block_var, ["3", "6"])
        add_check("Bloquear por calendario", cal_var)
        add_check("Bloquear por sentimiento", sent_var)
        add_check("FinBERT (opcional)", finbert_var)
        add_check("Notificaciones macOS", notify_var)
        add_check("Modo compacto", compact_var)

        def on_save() -> None:
            self.compact_mode = bool(compact_var.get())
            save_user_settings({
                "refresh_interval_seconds": int(refresh_var.get()),
                "calendar_block_hours": int(block_var.get()),
                "calendar_blocks_signals": cal_var.get(),
                "sentiment_blocks_signals": sent_var.get(),
                "use_finbert": finbert_var.get(),
                "macos_notifications": notify_var.get(),
                "compact_mode": self.compact_mode,
            })
            self.geometry("1040x700" if self.compact_mode else "1440x900")
            self._update_footer_status()
            self._schedule_refresh_loop()
            self._render_current()
            dialog.destroy()

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=16)
        self.action_button(actions, "Guardar", on_save, primary=True).pack(side="left", padx=(0, 8))
        self.action_button(actions, "Cancelar", dialog.destroy).pack(side="left")

    def _schedule_refresh_loop(self) -> None:
        if self.refresh_job is not None:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None
        if not self.auto_refresh_enabled:
            self._next_refresh_at = None
            return
        interval = self._refresh_interval_ms()
        self._next_refresh_at = time.time() + interval / 1000.0
        self.refresh_job = self.after(interval, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        """Timer real: sí dispara fetch (antes solo reprogramaba sin refrescar)."""
        self._start_fetch()
        self._schedule_refresh_loop()

    def _nav_keys(self) -> List[str]:
        return [k for k, _, _ in NAV_ITEMS]

    def _nav_by_index(self, idx: int) -> None:
        keys = self._nav_keys()
        if 0 <= idx < len(keys):
            self._set_view(keys[idx])

    def _nav_step(self, delta: int) -> None:
        keys = self._nav_keys()
        try:
            idx = keys.index(self.current_view)
        except ValueError:
            idx = 0
        self._set_view(keys[(idx + delta) % len(keys)])

    def _set_view(self, key: str) -> None:
        """Clic de menú: un solo render, sin debounce que deje estados a medias."""
        if key not in NAV_LABELS:
            key = "overview"
        if self._view_job is not None:
            try:
                self.after_cancel(self._view_job)
            except Exception:
                pass
            self._view_job = None
        self._apply_view(key)

    def _update_chrome(self, key: str) -> None:
        for k, btn in self.nav_buttons.items():
            active = k == key
            try:
                btn.configure(
                    fg_color=NAV_ACTIVE if active else NAV_IDLE,
                    bg_color=CHROME_BG,
                    text_color=TEXT if active else MUTED,
                    hover_color=NAV_ACTIVE_HOVER if active else CARD,
                )
            except Exception:
                pass
        self._paint_header_labels(key)

    def _apply_view(self, key: str) -> None:
        if key not in NAV_LABELS:
            key = "overview"
        self.current_view = key
        self._update_chrome(key)
        self._schedule_persist()
        self._render_current()

    # ─── Data fetch ───
    def _schedule_fetch(self, immediate: bool = False) -> None:
        if immediate:
            self._start_fetch()
        # Reprograma el ciclo de auto-refresh desde ahora
        self._schedule_refresh_loop()

    def _start_fetch(self) -> None:
        if self.fetch_in_progress:
            return
        self.fetch_in_progress = True
        self._set_status_chip("Actualizando…", TEXT, CHIP_NEUTRAL)
        self._set_status_text("Actualizando…", MUTED)
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
            self.after(0, lambda: self._on_fetch_success(snap, sig))
        except Exception as exc:
            self.after(0, lambda: self._on_fetch_error(exc))

    def _status_chip_style(self, status: str) -> Tuple[str, str]:
        value = (status or "").upper()
        color = status_color(value)
        if value == "BLOCKED":
            return color, CHIP_BAD
        if value == "HEALTHY":
            return color, CHIP_OK
        if value in {"CAUTION", "PANIC"}:
            return color, CHIP_WARN if value == "CAUTION" else CHIP_BAD
        return color, CHIP_NEUTRAL

    def _on_fetch_success(self, snap: Dict[str, Any], sig: str) -> None:
        changed = sig != self.current_signature
        notify_snapshot_change(self.current_snapshot, snap)
        self.fetch_in_progress = False
        self.last_error = None
        self.last_success_at = time.time()
        self._update_footer_status()
        status = str(snap["status"])
        color, chip_bg = self._status_chip_style(status)
        if changed:
            self.current_snapshot = snap
            self.current_signature = sig
            self._set_status_chip(status, color, chip_bg)
            self._set_status_text("Listo", GOOD)
            self._update_macro_label(snap)
            if self._view_job is None:
                self._render_current()
        else:
            self._set_status_chip(f"{status} · ok", color, chip_bg)
            self._set_status_text("Listo", GOOD)
            self._update_macro_label(snap)

    def _update_macro_label(self, snap: Dict[str, Any]) -> None:
        cal = check_macro_events()
        if cal.get("should_block_signals"):
            self._set_macro_chip(
                f"Bloqueo {cal.get('block_hours', CALENDAR_BLOCK_HOURS)}h",
                BAD,
                CHIP_BAD,
            )
        elif cal.get("next_event"):
            title = cal["next_event"].get("title", "Evento macro")
            self._set_macro_chip(f"Macro · {title[:28]}", WARN, CHIP_WARN)
        else:
            self._set_macro_chip("Macro libre", GOOD, CHIP_OK)

    def _on_fetch_error(self, exc: Exception) -> None:
        self.fetch_in_progress = False
        self.last_error = str(exc)
        self._set_status_chip("ERROR", BAD, CHIP_BAD)
        self._set_status_text("Error", BAD)
        if not self.current_snapshot:
            self._render_current()
        else:
            self.show_toast(f"Error al actualizar: {exc}", ok=False)

    # ─── Routing ───
    def _render_current(self) -> None:
        if self._switching:
            self._pending_render = True
            return
        self._switching = True
        self._pending_render = False
        self._render_gen += 1
        gen = self._render_gen
        view = self.current_view
        try:
            self._mount_content_host()
            if gen != self._render_gen or view != self.current_view:
                return
            if not self.current_snapshot:
                card = self.make_card(self.content, fill="both", expand=True, pady=8)
                msg = self.last_error or "Cargando snapshot…"
                ctk.CTkLabel(card, text=msg, text_color=BAD if self.last_error else MUTED, wraplength=520).pack(
                    padx=20, pady=(36, 12)
                )
                if self.last_error:
                    self.action_button(
                        card, "Reintentar", lambda: self._schedule_fetch(immediate=True), primary=True
                    ).pack(pady=(0, 28))
            else:
                {
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
                }[view](self.current_snapshot)
            if gen != self._render_gen:
                return
            try:
                self.update_idletasks()
            except Exception:
                pass
            self._safe_after(16, self._arm_content_scroll)
            self._safe_after(30, self._refresh_wraplengths)
        except Exception as exc:
            if gen == self._render_gen:
                try:
                    err = self.make_card(self.content, fill="x", pady=8)
                    self.body_text(err, f"Error al pintar la vista: {exc}", BAD)
                except Exception:
                    pass
        finally:
            self._switching = False
            if self._pending_render and self._alive:
                self._pending_render = False
                self.after(0, self._render_current)

    # ─── Overview (decision cockpit) ───
    def _view_overview(self, s: Dict[str, Any]) -> None:
        d = s["data"]
        dec = s["decision"]
        rot = s["rotation"]
        fx = d.get("Forex", {}).get("EURUSD", {})
        uup = d.get("Assets", {}).get("UUP", {})
        fx_sig = forex_signal(fx, uup, s.get("news_items", []))
        dual = forex_dual_perspective(fx_sig)
        rates = forex_bidirectional_rates(fx)
        ranked = sorted(dec.get("asset_scores", {}).values(), key=lambda m: m.get("score", 0), reverse=True)
        top_assets = ranked[:6]
        allocation = dec.get("allocation") or {}
        alloc_sorted = sorted(
            ((k, int(v)) for k, v in allocation.items() if int(v or 0) > 0),
            key=lambda item: item[1],
            reverse=True,
        )
        macro_action = dec.get("macro_action", dec.get("action"))
        ops_action = dec.get("operational_action", dec.get("action"))
        pause = dec.get("operational_pause_reason")
        score = int(dec.get("score", 0))
        rationale = str(dec.get("rationale") or "").strip()
        alerts = s.get("alerts") or []
        cal = check_macro_events()

        # 1) Acción ahora
        hero = self.make_card(self.content, fill="x", pady=3)
        self.section_title(hero, "ACCIÓN AHORA")
        head = ctk.CTkFrame(hero, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            head,
            text=str(ops_action),
            text_color=TEXT,
            font=ctk.CTkFont(family="SF Pro Display", size=26, weight="bold"),
            anchor="w",
        ).pack(side="left")
        conf = str(dec.get("confidence", "—"))
        conf_color = GOOD if conf.upper() == "ALTA" else (WARN if conf.upper() == "MEDIA" else MUTED)
        ctk.CTkLabel(
            head,
            text=f"  {conf}",
            text_color=conf_color,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(side="left", padx=(8, 0))
        if pause:
            self.kv_row(hero, "Pausa", str(pause), WARN)
        favored = ", ".join(dec.get("favored_assets") or ["—"])
        self.kv_row(hero, "Favorecidos", favored)
        self.kv_row(hero, "Macro", f"{macro_action} · score {score}/100", score_color(score))
        self.progress_row(hero, "Score", score / 100.0, f"{score}/100", color=score_color(score), label_width=78)
        if rationale:
            short = rationale if len(rationale) <= 320 else rationale[:317] + "…"
            self.body_text(hero, short, MUTED)

        # 2) Bloqueos / calendario + estado
        cols = self._grid_cols(2)
        risk = self.layout(fill="x", pady=(6, 0))
        for c in range(cols):
            risk.columnconfigure(c, weight=1)

        block_card = self.make_card(risk)
        block_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6 if cols > 1 else 0), pady=3)
        self.section_title(block_card, "RIESGO / FILTROS")
        self.kv_row(block_card, "Status", str(s.get("status")), status_color(str(s.get("status"))))
        if cal.get("should_block_signals"):
            self.kv_row(
                block_card,
                "Calendario",
                f"BLOQUEO {cal.get('block_hours', CALENDAR_BLOCK_HOURS)}h",
                BAD,
            )
        elif cal.get("next_event"):
            ev = cal["next_event"]
            self.kv_row(block_card, "Próximo", str(ev.get("title", "Evento"))[:42], WARN)
            when = str(ev.get("when") or ev.get("date") or ev.get("time") or "—")
            self.kv_row(block_card, "Cuándo", when[:42], MUTED)
        else:
            self.kv_row(block_card, "Calendario", "sin eventos cercanos", GOOD)
        if alerts:
            for alert in alerts[:3]:
                self.body_text(block_card, f"• {alert}", WARN if "bloque" in str(alert).lower() else MUTED, wrap=420)
        else:
            self.body_text(block_card, "Sin alertas activas.", GOOD, wrap=420)

        alloc_card = self.make_card(risk)
        alloc_card.grid(
            row=0 if cols > 1 else 1,
            column=1 if cols > 1 else 0,
            sticky="nsew",
            padx=(6 if cols > 1 else 0, 0),
            pady=3,
        )
        self.section_title(alloc_card, "ALLOCATION SUGERIDA", "clic → Activos")
        if not alloc_sorted:
            self.body_text(alloc_card, "Sin allocation (liquidez / datos insuficientes).", MUTED)
        else:
            for asset, pct in alloc_sorted[:7]:
                self.progress_row(alloc_card, asset, pct / 100.0, f"{pct}%", color=ACCENT if pct < 40 else GOOD)
        self.wire_click(alloc_card, lambda: self._set_view("assets"))

        # 3) Ranking + pulso
        mid = self.layout(fill="x", pady=(6, 0))
        for c in range(cols):
            mid.columnconfigure(c, weight=1)

        assets_p = self.make_card(mid)
        assets_p.grid(row=0, column=0, sticky="nsew", padx=(0, 6 if cols > 1 else 0), pady=3)
        self.section_title(assets_p, "RANKING ACTIVOS", "clic → detalle")
        for m in top_assets:
            sc = int(m.get("score", 0))
            label = str(m.get("label") or m.get("ticker") or "-")[:16]
            action = str(m.get("action") or "")
            self.progress_row(
                assets_p,
                label,
                sc / 100.0,
                f"{sc} {action[:10]}".strip(),
                color=score_color(sc),
                label_width=90,
            )
        self.wire_click(assets_p, lambda: self._set_view("assets"))

        pulse = self.make_card(mid)
        pulse.grid(
            row=0 if cols > 1 else 1,
            column=1 if cols > 1 else 0,
            sticky="nsew",
            padx=(6 if cols > 1 else 0, 0),
            pady=3,
        )
        self.section_title(pulse, "PULSO MACRO")
        for label, value, low, high, display in (
            ("VIX", d.get("VIX"), 10, 40, fmt(d.get("VIX"))),
            ("Bono 10Y", d.get("US10Y"), 2, 6, fmt(d.get("US10Y"), 2, "%")),
            ("IPC YoY", d.get("CPI_YoY_Pct"), 1, 6, fmt(d.get("CPI_YoY_Pct"), 1, "%")),
            ("M2", d.get("M2_Change_Pct"), -6, 8, signed(d.get("M2_Change_Pct"))),
            ("Curva", d.get("Yield_Curve_Spread"), -1, 2, signed(d.get("Yield_Curve_Spread"), suffix="pp")),
            (
                "Corr",
                abs(d.get("Correlation_Proxy")) if d.get("Correlation_Proxy") is not None else None,
                0,
                1,
                fmt(d.get("Correlation_Proxy"), 3),
            ),
        ):
            self.metric_progress(pulse, label, value, low, high, display)

        # 4) Rotación / Forex / News — drill-down
        bottom_cols = self._grid_cols(3)
        if self.winfo_width() >= 1280:
            bottom_cols = 3
        bottom = self.layout(fill="x", pady=(6, 8))
        for c in range(bottom_cols):
            bottom.columnconfigure(c, weight=1)

        def place(card: Any, idx: int) -> None:
            r, c = divmod(idx, bottom_cols)
            pad_l = 0 if c == 0 else 5
            pad_r = 0 if c == bottom_cols - 1 else 5
            card.grid(row=r, column=c, sticky="nsew", padx=(pad_l, pad_r), pady=3)

        rot_p = self.make_card(bottom)
        place(rot_p, 0)
        self.section_title(rot_p, "ROTACIÓN", "clic →")
        self.kv_row(rot_p, "Estado", str(rot.get("state", "—")))
        self.kv_row(rot_p, "Leaders 1M", signed(rot.get("leaders_avg_1m")))
        self.kv_row(rot_p, "Receivers 1M", signed(rot.get("receivers_avg_1m")))
        themes = rot.get("themes") or []
        if themes:
            t0 = themes[0]
            action0, _ = rotation_trade_action(t0)
            self.body_text(
                rot_p,
                f"{t0.get('theme', '')}: {action0} · {t0.get('signal', '')}",
                MUTED,
            )
        self.wire_click(rot_p, lambda: self._set_view("rotation"))

        fx_p = self.make_card(bottom)
        place(fx_p, 1)
        self.section_title(fx_p, "FOREX", "clic →")
        self.kv_row(fx_p, "Spot", rates["eur_label"])
        self.kv_row(fx_p, "Acción", str(fx_sig.get("action", "—")))
        self.kv_row(fx_p, "EUR", str(dual.get("eur_view", "—")))
        self.kv_row(fx_p, "Rel 1M", signed(fx_sig.get("rel_1m"), suffix="pp"))
        self.wire_click(fx_p, lambda: self._set_view("forex"))

        news_p = self.make_card(bottom)
        place(news_p, 2)
        self.section_title(news_p, "NEWS", "clic →")
        items = s.get("news_items") or []
        if not items:
            self.body_text(news_p, "Sin titulares.", MUTED)
        for item in items[:4]:
            title = str(item.get("title") or "-")
            if len(title) > 72:
                title = title[:69] + "…"
            self.body_text(news_p, f"[{item.get('source', 'RSS')}] {title}", TEXT)
        self.wire_click(news_p, lambda: self._set_view("news"))

    def _view_rotation(self, s: Dict[str, Any]) -> None:
        r = s["rotation"]
        themes = list(r.get("themes") or [])
        actions = [rotation_trade_action(t)[0] for t in themes]
        n_buy = actions.count("COMPRAR")
        n_wait = actions.count("ESPERAR")
        n_sell = actions.count("VENDER")

        head = self.make_card(self.content, fill="x", pady=3)
        self.section_title(head, "RESUMEN ROTACIÓN")
        self.kv_row(head, "Estado", str(r.get("state", "—")))
        self.kv_row(head, "Leaders 1M", signed(r.get("leaders_avg_1m")))
        self.kv_row(head, "Receivers 1M", signed(r.get("receivers_avg_1m")))
        counts = tk.Frame(head, bg=CARD)
        counts.pack(fill="x", padx=14, pady=(4, 8))
        for label, n, color in (
            ("COMPRAR", n_buy, GOOD),
            ("ESPERAR", n_wait, MUTED),
            ("VENDER", n_sell, BAD),
        ):
            chip = ctk.CTkLabel(
                counts,
                text=f"  {label} {n}  ",
                text_color=color,
                fg_color=CHIP_OK if color == GOOD else (CHIP_BAD if color == BAD else CHIP_NEUTRAL),
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            chip.pack(side="left", padx=(0, 8))
        if r.get("summary"):
            self.body_text(head, str(r.get("summary")), MUTED)

        # Tabla 100% tk (CTk anidado deformaba los mini-recuadros al resize)
        table = tk.Frame(self.content, bg=CARD, highlightthickness=0, bd=0)
        table.pack(fill="x", pady=3)
        tk.Label(
            table,
            text="SECTORES · ACCIÓN",
            bg=CARD,
            fg=ACCENT,
            anchor="w",
            font=("SF Pro Text", 12, "bold"),
        ).pack(fill="x", padx=14, pady=(12, 6))

        def add_group(title: str, items: List[Dict[str, Any]]) -> None:
            if not items:
                return
            tk.Label(
                table,
                text=title,
                bg=CARD,
                fg=ACCENT,
                anchor="w",
                font=("SF Pro Text", 11, "bold"),
            ).pack(fill="x", padx=14, pady=(10, 4))
            for t in items:
                action, color = rotation_trade_action(t)
                row = tk.Frame(table, bg=CARD_INNER, highlightthickness=0, bd=0)
                row.pack(fill="x", padx=10, pady=3)
                pad = tk.Frame(row, bg=CARD_INNER)
                pad.pack(fill="x", padx=10, pady=8)
                cols = [
                    (str(t.get("theme", "—"))[:22], TEXT, 22, ("SF Pro Text", 12)),
                    (str(t.get("ticker", "—")), MUTED, 7, ("Menlo", 11)),
                    (action, color, 9, ("SF Pro Text", 12, "bold")),
                    (str(t.get("signal", "—"))[:26], MUTED, 26, ("SF Pro Text", 11)),
                    (signed(t.get("momentum_1m")), TEXT, 8, ("Menlo", 11)),
                    (signed(t.get("relative_1m_vs_spy")), TEXT, 8, ("Menlo", 11)),
                ]
                for text, fg, width, font in cols:
                    tk.Label(
                        pad,
                        text=text,
                        bg=CARD_INNER,
                        fg=fg,
                        anchor="w",
                        width=width,
                        font=font,
                    ).pack(side="left", padx=2)
            # spacer inferior del grupo
            tk.Frame(table, bg=CARD, height=4).pack(fill="x")

        add_group("LÍDERES", [t for t in themes if t.get("group") == "Líderes en descanso"])
        add_group("RECEPTORES DE FLUJO", [t for t in themes if t.get("group") != "Líderes en descanso"])
        if not themes:
            tk.Label(table, text="Sin temas de rotación disponibles.", bg=CARD, fg=MUTED, anchor="w").pack(
                fill="x", padx=14, pady=10
            )
        tk.Frame(table, bg=CARD, height=10).pack(fill="x")

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

        top = self.layout(fill="x")
        top.columnconfigure((0, 1, 2), weight=1)

        spot = self.make_card(top)
        spot.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=3)
        self.section_title(spot, "TIPO DE CAMBIO")
        ctk.CTkLabel(spot, text=rates["eur_label"], text_color=TEXT, font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(
            fill="x", padx=14
        )
        self.kv_row(spot, "USD/EUR", rates["usd_label"])
        self.kv_row(spot, "Acción", str(fx_sig.get("action")))
        self.kv_row(spot, "Confianza", f"{fx_sig.get('confidence')} ({fx_sig.get('score'):+d})")

        eur = self.make_card(top)
        eur.grid(row=0, column=1, sticky="nsew", padx=6, pady=3)
        self.section_title(eur, "EUR/USD")
        self.kv_row(eur, "Spot", fmt(fx.get("price"), 4))
        self.kv_row(eur, "MA20/50", f"{fmt(fx.get('ma20'), 4)} / {fmt(fx.get('ma50'), 4)}")
        self.kv_row(eur, "Trend", str(fx_sig.get("eur_trend")))
        self.metric_progress(eur, "Mom 1M", fx.get("momentum_1m"), -5, 5, signed(fx.get("momentum_1m")))
        self.metric_progress(eur, "Mom 3M", fx.get("momentum_3m"), -10, 10, signed(fx.get("momentum_3m")))
        self.kv_row(eur, "Vista", f"{eur_sem['label']} · {dual['eur_view']}")

        usd = self.make_card(top)
        usd.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=3)
        self.section_title(usd, "USD (UUP)")
        self.kv_row(usd, "Spot", fmt(uup.get("price"), 2))
        self.kv_row(usd, "Trend", str(fx_sig.get("usd_trend")))
        self.metric_progress(usd, "Mom 1M", uup.get("momentum_1m"), -5, 5, signed(uup.get("momentum_1m")))
        self.kv_row(usd, "Score", f"{uup_score if uup_score is not None else '—'}/100")
        self.kv_row(usd, "Vista", f"{usd_sem['label']} · {dual['usd_view']}")

        rel = self.make_card(self.content, fill="x", pady=3)
        self.section_title(rel, "RELATIVO EUR vs USD · NEWS")
        self.metric_progress(rel, "Dif 1M", fx_sig.get("rel_1m"), -5, 5, signed(fx_sig.get("rel_1m"), suffix="pp"))
        self.kv_row(rel, "Evolución", f"{signed(fx_sig.get('rel_change'), suffix='pp')} → {fx_sig.get('evolution')}")
        news = fx_sig.get("news", {})
        self.kv_row(
            rel,
            "News neto",
            f"EUR {news.get('eur_score', 0):+d} / USD {news.get('usd_score', 0):+d} → {news.get('net_eur_minus_usd', 0):+d}",
        )
        self.body_text(rel, str(news.get("expectation", "")))

    def _view_assets(self, s: Dict[str, Any]) -> None:
        assets = sorted(
            s["decision"].get("asset_scores", {}).items(),
            key=lambda item: item[1].get("score", 0),
            reverse=True,
        )
        for _, m in assets:
            score = int(m.get("score", 0))
            panel = self.make_card(self.content, fill="x", pady=3)
            head = ctk.CTkFrame(panel, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(12, 2))
            ctk.CTkLabel(head, text=str(m.get("label") or "-"), text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(
                side="left"
            )
            ctk.CTkLabel(head, text=f"{score}/100", text_color=score_color(score), font=ctk.CTkFont(size=13, weight="bold")).pack(
                side="right"
            )
            self.progress_row(panel, "Score", score / 100.0, f"{score}/100", color=score_color(score))
            self.kv_row(panel, "Acción", str(m.get("action") or "—"))
            self.kv_row(panel, "Trend", str(m.get("trend") or "—"))
            self.kv_row(panel, "Mom 1M / 3M", f"{signed(m.get('momentum_1m'))}  /  {signed(m.get('momentum_3m'))}")
            self.kv_row(panel, "Vol 20d", signed(m.get("volatility_20d")))

    def _view_global(self, s: Dict[str, Any]) -> None:
        markets = s["data"].get("GlobalMarkets", {}) or {}
        grid = self.layout(fill="x")
        cols = 2
        for idx, (region, metrics) in enumerate(markets.items()):
            r, c = divmod(idx, cols)
            panel = self.make_card(grid)
            panel.grid(row=r, column=c, sticky="nsew", padx=5, pady=5)
            grid.columnconfigure(c, weight=1)
            self.section_title(panel, region.upper())
            self.kv_row(panel, "Spot", fmt(metrics.get("price"), 2))
            self.kv_row(panel, "MA20 / MA50", f"{fmt(metrics.get('ma20'), 2)} / {fmt(metrics.get('ma50'), 2)}")
            self.kv_row(panel, "Trend", trend_from_metrics(metrics))
            self.metric_progress(panel, "Mom 1M", metrics.get("momentum_1m"), -8, 8, signed(metrics.get("momentum_1m")))
            self.metric_progress(panel, "Mom 3M", metrics.get("momentum_3m"), -12, 12, signed(metrics.get("momentum_3m")))
        if not markets:
            panel = self.make_card(self.content, fill="x")
            self.body_text(panel, "Sin datos de mercados globales.")

    def _view_news(self, s: Dict[str, Any]) -> None:
        items = s.get("news_items") or []
        head = self.make_card(self.content, fill="x", pady=3)
        self.section_title(head, f"NOTICIAS · {len(items)} titulares")
        for item in items[:80]:
            row = self.make_card(self.content, fill="x", pady=2)
            meta = ctk.CTkFrame(row, fg_color="transparent")
            meta.pack(fill="x", padx=14, pady=(10, 0))
            ctk.CTkLabel(meta, text=str(item.get("source") or "RSS"), text_color=ACCENT, font=ctk.CTkFont(size=11)).pack(
                side="left"
            )
            ctk.CTkLabel(
                meta, text=str(item.get("published_at") or "—")[:22], text_color=MUTED, font=ctk.CTkFont(size=11)
            ).pack(side="right")
            self.body_text(row, str(item.get("title") or "-"))

    def _view_history(self, s: Dict[str, Any]) -> None:
        summary = summarize_history(limit=30)
        head = self.make_card(self.content, fill="x", pady=3)
        self.section_title(head, "HISTORIAL DE DECISIONES")
        if summary["count"] == 0:
            self.body_text(head, "No hay historial todavía. Ejecuta NEXUS con exportación activa.")
            return
        self.kv_row(head, "Snapshots", str(summary["count"]))
        self.kv_row(
            head,
            "Score medio",
            f"{summary.get('avg_score')}  (min {summary.get('min_score')} / max {summary.get('max_score')})",
        )

        cols = self.layout(fill="x", pady=3)
        cols.columnconfigure((0, 1), weight=1)
        left = self.make_card(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right = self.make_card(cols)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.section_title(left, "EVOLUCIÓN RECIENTE")
        for point in summary.get("score_timeline", [])[-12:][::-1]:
            macro = point.get("macro_action") or point.get("action")
            ops = point.get("operational_action") or point.get("action")
            stamp = str(point.get("captured_at") or "")[:19]
            label = f"{macro}" if macro == ops else f"M:{macro} / O:{ops}"
            self.kv_row(left, stamp, f"score {point.get('score')} · {label}")
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
        head = self.layout(fill="x")
        head.columnconfigure((0, 1, 2), weight=1)

        p1 = self.make_card(head)
        p1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=3)
        self.section_title(p1, "PAPER VALUE")
        self.kv_row(p1, "Inicial", f"${portfolio.get('starting_value', 0):,.2f}")
        self.kv_row(p1, "Actual", f"${portfolio.get('current_value', 0):,.2f}")
        self.kv_row(p1, "Retorno", f"{summary['total_return_pct']:+.2f}%", GOOD if summary["total_return_pct"] >= 0 else BAD)

        p2 = self.make_card(head)
        p2.grid(row=0, column=1, sticky="nsew", padx=6, pady=3)
        self.section_title(p2, "BENCHMARK SPY")
        self.kv_row(p2, "Buy&Hold", f"{summary['benchmark_return_pct']:+.2f}%")
        self.kv_row(p2, "Alpha", f"{summary['alpha_vs_spy_pct']:+.2f}%", GOOD if summary["alpha_vs_spy_pct"] >= 0 else BAD)
        self.kv_row(p2, "Última acción", f"{portfolio.get('last_action')} ({portfolio.get('last_score')})")

        p3 = self.make_card(head)
        p3.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=3)
        self.section_title(p3, "POSICIÓN")
        holdings = portfolio.get("holdings") or {}
        if not holdings:
            self.body_text(p3, "Sin posiciones.")
        for asset, amount in sorted(holdings.items()):
            self.kv_row(p3, asset, f"${amount:,.2f}" if asset == "CASH" else f"{amount:.4f}")

        trades_p = self.make_card(self.content, fill="x", pady=3)
        self.section_title(trades_p, f"ÚLTIMOS TRADES ({summary['trade_count']})")
        for trade in (summary.get("trades") or [])[::-1][:12]:
            stamp = str(trade.get("captured_at") or trade.get("timestamp") or "")[:19]
            action = trade.get("action") or trade.get("side") or "—"
            detail = trade.get("detail") or trade.get("allocation") or ""
            self.kv_row(trades_p, stamp, f"{action}  {detail}")

    def _view_track(self, s: Dict[str, Any]) -> None:
        payload = track_record_chart_payload(forward_days=5, limit=100, chart_limit=40)
        self._track_chart_payload = payload

        summary = self.make_card(self.content, fill="x", pady=3)
        self.section_title(summary, "TRACK RECORD vs SPY")
        if payload.get("sample_size", 0) == 0:
            self.body_text(summary, payload.get("message", "Sin datos de track record."))
        else:
            cols = ctk.CTkFrame(summary, fg_color="transparent")
            cols.pack(fill="x", padx=6, pady=(0, 8))
            cols.columnconfigure((0, 1), weight=1)
            left = ctk.CTkFrame(cols, fg_color="transparent")
            left.grid(row=0, column=0, sticky="nsew")
            right = ctk.CTkFrame(cols, fg_color="transparent")
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

        chart_card = self.make_card(self.content, fill="x", pady=3)
        canvas_host = ctk.CTkFrame(chart_card, fg_color=CARD, corner_radius=INNER_CORNER)
        canvas_host.pack(fill="x", padx=10, pady=10)
        canvas = tk.Canvas(canvas_host, bg=CARD, highlightthickness=0, height=230)
        canvas.pack(fill="both", expand=True)
        self.track_canvas = canvas
        canvas.bind("<Configure>", lambda _e: self._redraw_track_chart_if_visible())
        self._draw_track_chart(payload)

        recent = self.make_card(self.content, fill="x", pady=3)
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
            canvas.create_text(width // 2, height // 2, text=payload.get("message", "Sin datos"), fill=MUTED)
            return

        left_w = int(width * 0.28)
        canvas.create_text(pad, pad, text="ACIERTO %", anchor="nw", fill=ACCENT)
        bar_top = pad + 28
        max_bar_w = left_w - pad * 2 - 70
        for idx, item in enumerate(payload.get("hit_bars", [])):
            y = bar_top + idx * 36
            value = item.get("value")
            color = GOOD if item.get("color") == "good" else WARN
            canvas.create_text(pad, y, text=f"{item.get('label')} (n={item.get('count', 0)})", anchor="nw", fill=MUTED)
            canvas.create_rectangle(pad, y + 16, pad + max_bar_w, y + 38, outline=LINE, fill=CARD_INNER)
            if value is not None:
                fill_w = max(2, int(max_bar_w * max(0.0, min(100.0, float(value))) / 100.0))
                canvas.create_rectangle(pad, y + 16, pad + fill_w, y + 38, outline="", fill=color)
                canvas.create_text(pad + max_bar_w + 8, y + 27, text=f"{value:.0f}%", anchor="w", fill=TEXT)
            else:
                canvas.create_text(pad + max_bar_w + 8, y + 27, text="—", anchor="w", fill=MUTED)

        right_x0 = left_w + 8
        right_x1 = width - pad
        chart_top = pad + 24
        chart_bottom = height - pad - 18
        zero_y = (chart_top + chart_bottom) / 2
        samples = payload.get("chart_samples") or []
        canvas.create_text(
            right_x0,
            pad,
            text=f"SPY forward {payload.get('forward_days', 5)}d  (últimas {len(samples)})",
            anchor="nw",
            fill=ACCENT,
        )
        canvas.create_line(right_x0, chart_top, right_x0, chart_bottom, fill=LINE)
        canvas.create_line(right_x0, chart_bottom, right_x1, chart_bottom, fill=LINE)
        canvas.create_line(right_x0, zero_y, right_x1, zero_y, fill=LINE, dash=(3, 3))
        if not samples:
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

    def _view_report(self, s: Dict[str, Any]) -> None:
        panel = self.make_card(self.content, fill="both", expand=True, pady=3)
        self.section_title(panel, "INFORME DIARIO")
        text = ctk.CTkTextbox(
            panel,
            fg_color=CARD_INNER,
            text_color=TEXT,
            corner_radius=INNER_CORNER,
            font=ctk.CTkFont(family="Menlo", size=12),
        )
        text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        text.insert("1.0", format_daily_report(s))
        text.configure(state="disabled")

    def _view_quality(self, s: Dict[str, Any]) -> None:
        q = s["data"].get("DataQuality", {}) or {}
        if not q:
            panel = self.make_card(self.content, fill="x")
            self.body_text(panel, "Sin metadatos de calidad.")
            return
        for key, meta in q.items():
            status = str(meta.get("status") or "-")
            color = GOOD if status == "OK" else (WARN if status == "STALE" else BAD)
            panel = self.make_card(self.content, fill="x", pady=2)
            head = ctk.CTkFrame(panel, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(head, text=key, text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(head, text=status, text_color=color, font=ctk.CTkFont(size=12, weight="bold")).pack(side="right")
            self.kv_row(panel, "Source", str(meta.get("source") or "—"))
            detail = meta.get("detail") or ""
            if detail:
                self.body_text(panel, str(detail), MUTED)


def main() -> None:
    _configure_windows_dpi_awareness()
    app = NexusDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
