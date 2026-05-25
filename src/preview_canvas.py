"""Виджеты предпросмотра Tkinter."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from PIL import Image, ImageOps, ImageTk


def pil_to_display_rgb(im: Image.Image) -> Image.Image:
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (238, 242, 248))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[3])
        return bg
    return im.convert("RGB")


class ResizingPreviewCanvas(tk.Canvas):

    def __init__(self, master: tk.Widget, **kw: Any) -> None:
        super().__init__(
            master,
            bg="#f1f5f9",
            highlightthickness=0,
            **kw,
        )
        self._source: Image.Image | None = None
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._job: str | None = None
        self.bind("<Configure>", self._on_configure)

    def _cancel_pending(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def clear_placeholder(self, hint: str) -> None:
        self._source = None
        self._cancel_pending()
        self._schedule_draw_placeholder(hint)

    def _schedule_draw_placeholder(self, hint: str) -> None:
        self._cancel_pending()

        def draw() -> None:
            self._job = None
            self.delete("all")
            self._photo_ref = None
            cw = max(int(self.winfo_width()), 40)
            ch = max(int(self.winfo_height()), 40)
            self.create_text(
                cw // 2,
                ch // 2,
                text=hint,
                fill="#475569",
                justify=tk.CENTER,
                font=("Segoe UI", 11),
                width=max(cw - 24, 40),
            )

        self._job = self.after_idle(draw)

    def set_source_pil(self, im: Image.Image) -> None:
        self._cancel_pending()
        self._source = pil_to_display_rgb(im)
        self._schedule_draw_fit()

    def _on_configure(self, _event: tk.Event | None = None) -> None:
        if self._source is not None:
            self._schedule_draw_fit()

    def _schedule_draw_fit(self) -> None:
        if self._source is None:
            return
        self._cancel_pending()
        self._job = self.after(85, self._draw_fit)

    def _draw_fit(self) -> None:
        self._job = None
        if self._source is None:
            return
        cw = max(int(self.winfo_width()), 40)
        ch = max(int(self.winfo_height()), 40)
        im = ImageOps.contain(self._source, (max(cw - 8, 1), max(ch - 8, 1)), Image.Resampling.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(im)
        self.delete("all")
        self.create_image(cw // 2, ch // 2, image=self._photo_ref)


class ZoomPanPreviewCanvas(tk.Canvas):

    MIN_ZOOM = 0.12
    MAX_ZOOM = 20.0

    def __init__(self, master: tk.Widget, **kw: Any) -> None:
        super().__init__(
            master,
            bg="#eef0f3",
            highlightthickness=1,
            highlightbackground="#c9ccd4",
            takefocus=True,
            **kw,
        )
        self._source: Image.Image | None = None
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_last: tuple[int, int] | None = None

        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<MouseWheel>", self._wheel_win)
        self.bind("<Button-4>", self._wheel_x11_up)
        self.bind("<Button-5>", self._wheel_x11_down)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Enter>", lambda _e: self.focus_set())

    def clear(self) -> None:
        self._source = None
        self._photo_ref = None
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0
        self._drag_last = None
        self.delete("all")

    def set_source_pil_rgb(self, im: Image.Image) -> None:
        self._source = pil_to_display_rgb(im)
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0
        self._drag_last = None
        self.redraw()

    def _wheel_win(self, event: tk.Event) -> None:
        if self._source is None:
            return
        delta = int(getattr(event, "delta", 0))
        if delta > 0:
            self._apply_zoom(1.1)
        elif delta < 0:
            self._apply_zoom(1 / 1.1)

    def _wheel_x11_up(self, _event: tk.Event) -> None:
        if self._source:
            self._apply_zoom(1.1)

    def _wheel_x11_down(self, _event: tk.Event) -> None:
        if self._source:
            self._apply_zoom(1 / 1.1)

    def _apply_zoom(self, factor: float) -> None:
        nv = self._zoom * factor
        nv = max(self.MIN_ZOOM, min(self.MAX_ZOOM, nv))
        if abs(nv - self._zoom) < 1e-9:
            return
        self._zoom = nv
        self.redraw()

    def _press(self, event: tk.Event) -> None:
        self._drag_last = (event.x, event.y)

    def _motion(self, event: tk.Event) -> None:
        if self._drag_last is None or self._source is None:
            return
        dx = event.x - self._drag_last[0]
        dy = event.y - self._drag_last[1]
        self._drag_last = (event.x, event.y)
        self._pan_x += dx
        self._pan_y += dy
        self.redraw()

    def _release(self, _event: tk.Event) -> None:
        self._drag_last = None

    def redraw(self) -> None:
        if self._source is None:
            self.delete("all")
            return
        cw = max(int(self.winfo_width()), 20)
        ch = max(int(self.winfo_height()), 20)
        iw, ih = self._source.size
        if iw < 1 or ih < 1:
            return
        fit = min(cw / float(iw), ch / float(ih))
        scale = fit * self._zoom
        nw = max(1, int(round(iw * scale)))
        nh = max(1, int(round(ih * scale)))
        resized = self._source.resize((nw, nh), Image.Resampling.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(resized)
        self.delete("all")
        x = (cw - nw) // 2 + int(self._pan_x)
        y = (ch - nh) // 2 + int(self._pan_y)
        self.create_image(x, y, image=self._photo_ref, anchor=tk.NW)
