"""
Liquid-glass / vibrancy macOS para NEXUS.

Estrategia que sí funciona con Tk:
- Shell en tk.Frame/Canvas con bg=systemTransparent (sin CTkCanvas negros)
- Cards CTk opacas encima
- Blur real: CGSSetWindowBackgroundBlurRadius (SkyLight)

CustomTkinter NO puede ser el fondo: sus CTkCanvas tapan el blur.
"""

from __future__ import annotations

import os
import sys
from ctypes import c_int32, c_uint32, c_void_p, cdll
from typing import Any, Callable


TRANSPARENT = "systemTransparent" if sys.platform == "darwin" else "#141416"
DEFAULT_BLUR_RADIUS = 60

_sky = None
_conn_fn = None
_blur_fn = None
_last_window_number: int | None = None


def _load_skylight() -> bool:
    global _sky, _conn_fn, _blur_fn
    if _blur_fn is not None:
        return True
    if sys.platform != "darwin":
        return False
    try:
        _sky = cdll.LoadLibrary("/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight")
        _conn_fn = _sky.CGSDefaultConnectionForThread
        _conn_fn.restype = c_void_p
        _blur_fn = _sky.CGSSetWindowBackgroundBlurRadius
        _blur_fn.argtypes = [c_void_p, c_uint32, c_int32]
        _blur_fn.restype = c_int32
        return True
    except Exception:
        _sky = None
        _conn_fn = None
        _blur_fn = None
        return False


def _window_number_for_pid(pid: int, title_hint: str = "") -> int | None:
    try:
        import Quartz
    except Exception:
        return None

    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    info = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
    hint = (title_hint or "").strip().lower()
    candidates: list[tuple[int, int]] = []
    for win in info:
        if int(win.get("kCGWindowOwnerPID") or 0) != pid:
            continue
        bounds = win.get("kCGWindowBounds") or {}
        width = float(bounds.get("Width") or 0)
        height = float(bounds.get("Height") or 0)
        if width < 180 or height < 140:
            continue
        num = win.get("kCGWindowNumber")
        if not num:
            continue
        name = str(win.get("kCGWindowName") or "").lower()
        score = int(width * height)
        if hint and hint in name:
            score += 10_000_000
        if "nexus" in name:
            score += 1_000_000
        candidates.append((score, int(num)))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def set_background_blur(window_number: int, radius: int = DEFAULT_BLUR_RADIUS) -> bool:
    if not _load_skylight() or _blur_fn is None or _conn_fn is None:
        return False
    try:
        result = _blur_fn(_conn_fn(), c_uint32(int(window_number)), c_int32(int(radius)))
        return int(result) == 0
    except Exception:
        return False


def enable_window_transparency(tk_window: Any) -> None:
    if sys.platform != "darwin":
        return
    try:
        tk_window.attributes("-alpha", 1.0)
    except Exception:
        pass
    try:
        tk_window.attributes("-transparent", True)
    except Exception:
        pass
    # CTk: fg_color pinta el bg de Tk; systemTransparent deja pasar el blur.
    for key, value in (("fg_color", TRANSPARENT), ("bg", TRANSPARENT)):
        try:
            tk_window.configure(**{key: value})
        except Exception:
            pass
    try:
        import tkinter as tk

        tk.Tk.configure(tk_window, bg=TRANSPARENT)
    except Exception:
        pass


def apply_macos_vibrancy(
    tk_window: Any,
    *,
    radius: int = DEFAULT_BLUR_RADIUS,
    title_hint: str = "NEXUS",
) -> bool:
    global _last_window_number
    if sys.platform != "darwin":
        return False
    enable_window_transparency(tk_window)
    try:
        tk_window.update_idletasks()
    except Exception:
        pass
    number = _window_number_for_pid(os.getpid(), title_hint=title_hint or str(tk_window.title()))
    if number is None:
        return False
    _last_window_number = number
    ok = set_background_blur(number, radius=radius)
    # Refuerzo inmediato: algunos builds de Tk pierden el flag al redibujar
    if ok:
        enable_window_transparency(tk_window)
        set_background_blur(number, radius=radius)
    return ok


def schedule_vibrancy(
    tk_window: Any,
    *,
    radius: int = DEFAULT_BLUR_RADIUS,
    title_hint: str = "NEXUS",
    retries: int = 20,
    delay_ms: int = 160,
) -> None:
    if sys.platform != "darwin":
        return
    enable_window_transparency(tk_window)
    state = {"left": retries}

    def attempt() -> None:
        if not tk_window.winfo_exists():
            return
        ok = apply_macos_vibrancy(tk_window, radius=radius, title_hint=title_hint)
        if ok:
            # Refuerzo cuando la UI ya pintó cards
            def boost() -> None:
                if not tk_window.winfo_exists():
                    return
                enable_window_transparency(tk_window)
                if _last_window_number is not None:
                    set_background_blur(_last_window_number, radius)

            tk_window.after(350, boost)
            return
        state["left"] -= 1
        if state["left"] > 0:
            tk_window.after(delay_ms, attempt)

    tk_window.after(delay_ms, attempt)


def bind_vibrancy_keep_alive(
    tk_window: Any,
    *,
    radius: int = DEFAULT_BLUR_RADIUS,
    title_hint: str = "NEXUS",
) -> None:
    """Solo en Map — nunca en Configure (evita trompicones)."""
    if sys.platform != "darwin":
        return

    def on_map(_event: Any = None) -> None:
        if not tk_window.winfo_exists():
            return
        tk_window.after(
            80,
            lambda: apply_macos_vibrancy(tk_window, radius=radius, title_hint=title_hint)
            if tk_window.winfo_exists()
            else None,
        )

    tk_window.bind("<Map>", on_map, add="+")


class GlassScrollHost:
    """Área scroll con fondo de cristal (tk puro, sin CTkCanvas)."""

    def __init__(self, master: Any):
        import tkinter as tk

        self.outer = tk.Frame(master, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas = tk.Canvas(
            self.outer,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
            borderwidth=0,
        )
        self.inner = tk.Frame(self.canvas, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.pack(fill="both", expand=True)

        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.canvas.bind("<Configure>", self._sync_width)
        self._bind_wheel(self.outer)
        self._bind_wheel(self.canvas)
        self._bind_wheel(self.inner)

    def pack(self, **kwargs: Any) -> None:
        self.outer.pack(**kwargs)

    def _sync_scrollregion(self, _event: Any = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event: Any) -> None:
        self.canvas.itemconfigure(self._window_id, width=max(event.width, 1))

    def _on_wheel(self, event: Any) -> str:
        delta = getattr(event, "delta", 0) or 0
        if sys.platform == "darwin":
            steps = int(-delta)
        else:
            steps = int(-delta / 120) if delta else 0
        if steps == 0 and getattr(event, "num", None) in (4, 5):
            steps = -3 if event.num == 4 else 3
        if steps:
            self.canvas.yview_scroll(steps, "units")
        return "break"

    def _bind_wheel(self, widget: Any) -> None:
        widget.bind("<MouseWheel>", self._on_wheel, add="+")
        widget.bind("<Button-4>", self._on_wheel, add="+")
        widget.bind("<Button-5>", self._on_wheel, add="+")

    def arm_wheel_tree(self, widget: Any | None = None) -> None:
        """Re-bind wheel tras recrear hijos (cards CTk)."""
        root = widget or self.inner

        def walk(w: Any) -> None:
            self._bind_wheel(w)
            try:
                children = w.winfo_children()
            except Exception:
                return
            for child in children:
                walk(child)

        walk(root)

    def clear(self) -> None:
        for child in self.inner.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self.canvas.yview_moveto(0)
        self._sync_scrollregion()

    def yview_moveto(self, fraction: float) -> None:
        self.canvas.yview_moveto(fraction)


def glass_frame(master: Any, **pack) -> Any:
    import tkinter as tk

    frame = tk.Frame(master, bg=TRANSPARENT, highlightthickness=0, bd=0)
    if pack:
        frame.pack(**pack)
    return frame


def glass_label(master: Any, text: str, **kwargs: Any) -> Any:
    import tkinter as tk

    opts = {
        "text": text,
        "bg": TRANSPARENT,
        "fg": kwargs.pop("fg", "#FFFFFF"),
        "anchor": kwargs.pop("anchor", "w"),
        "justify": kwargs.pop("justify", "left"),
    }
    font = kwargs.pop("font", None)
    if font is not None:
        opts["font"] = font
    opts.update(kwargs)
    return tk.Label(master, **opts)
