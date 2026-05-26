"""Мастер сжатия изображений (Tkinter)."""

from __future__ import annotations

import os
import platform
import sys
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk
from typing import cast

_SRCP = Path(__file__).resolve().parent
if str(_SRCP) not in sys.path:
    sys.path.insert(0, str(_SRCP))

import image_pipeline as ip
import preview_worker as pw
from manual_settings import (
    ManualCompressionSettings,
    MAX_LONG_EDGE,
    MIN_LONG_EDGE_WHEN_LIMIT,
    clamp_manual,
)
from presets import CompressionPreset, preset_params
from preview_canvas import ResizingPreviewCanvas, ZoomPanPreviewCanvas

try:
    from tkinterdnd2 import DND_FILES
    from tkinterdnd2 import TkinterDnD as _TkDnd

    RootCls = _TkDnd.Tk  # type: ignore[attr-defined]
    _HAS_DND = True
except ImportError:
    RootCls = tk.Tk  # type: ignore[misc]
    _HAS_DND = False

APP_TITLE = "Сжатие изображений (локально)"
APP_NAME_RU = "Мастер сжатия изображений"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "Локальное пошаговое приложение для Windows: уменьшение размера и разрешения "
    "одного статичного изображения и сохранение в нужном формате. Интернет не нужен."
)
REPOSITORY_URL = "https://github.com/ppvikentiy/compess"

FINAL_PREVIEW_LONG_EDGE = 1400

STEP1_PREVIEW_HINT = "Перетащите файл сюда или нажмите «Открыть файл»."

PRESET_ORDER: list[CompressionPreset] = [
    CompressionPreset.WEAK,
    CompressionPreset.MEDIUM,
    CompressionPreset.STRONG,
    CompressionPreset.EXTREME,
]

STEP2_HINT = (
    "Пресеты — оценка для каждого варианта. Вручную — длинная сторона и качество; "
    "параметр качества относится к формату, выбранному на шаге 4."
)


def fmt_to_ext(fmt: ip.OutputFormat) -> str:
    return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}[fmt]


def human_bytes(n: int) -> str:
    units = ["Б", "КБ", "МБ", "ГБ"]
    v = float(n)
    ui = 0
    while v >= 2048 and ui < len(units) - 1:
        v /= 1024.0
        ui += 1
    if ui == 0:
        return f"{int(n)} Б"
    return f"{v:.1f} {units[ui]}"


class CompressWizardApp:
    def __init__(self) -> None:
        self.root: tk.Tk = RootCls()
        self.root.title(APP_TITLE)
        self.root.geometry("960x660")
        self.root.minsize(840, 560)

        self._estimate_running = False
        self._preview_running = False

        self.step1_preview_hint = STEP1_PREVIEW_HINT

        self.raw_path = ""
        self.pil_normalized = None
        self.source_bytes_on_disk = 0

        self.alpha_bg = "white"

        self.strip_meta = tk.BooleanVar(value=False)
        self.optimize_visuals = tk.BooleanVar(value=False)

        self._output_format_var = tk.StringVar(value="JPEG")

        self.out_folder = tk.StringVar(value=os.path.expanduser(r"~\Desktop"))
        self.out_filename = tk.StringVar(value="")

        self.compression_mode_var = tk.StringVar(value="preset")
        self.manual_no_resize = tk.BooleanVar(value=False)
        self.manual_edge_var = tk.StringVar(value="2048")
        self.manual_jpeg_val = tk.IntVar(value=82)
        self.manual_webp_val = tk.IntVar(value=78)
        self.manual_png_val = tk.IntVar(value=6)
        self.manual_estimate_var = tk.StringVar(value="…")

        bf = tkfont.nametofont("TkDefaultFont").copy()
        bf.configure(size=10)
        self.root.option_add("*Font", bf)

        st = ttk.Style()
        st.configure("Muted.TLabel", foreground="#454545")

        main = ttk.Frame(self.root, padding=14)
        main.pack(fill=tk.BOTH, expand=True)

        top_bar = ttk.Frame(main)
        top_bar.pack(fill=tk.X, anchor=tk.NE, pady=(0, 4))
        ttk.Button(top_bar, text="О Программе", command=self._show_about_program).pack(
            side=tk.RIGHT,
            padx=(6, 0),
        )
        ttk.Button(top_bar, text="О Разработчике", command=self._show_about_developer).pack(
            side=tk.RIGHT,
        )

        self.step_title = ttk.Label(
            main,
            text="",
            font=("Segoe UI Semibold", 13, "bold"),
        )
        self.step_title.pack(anchor="w")

        self.busy_banner = tk.StringVar(value="")
        ttk.Label(main, textvariable=self.busy_banner, foreground="#b00020").pack(
            anchor="w",
            pady=(2, 4),
        )

        self.container = tk.Frame(main)
        self.container.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        footer = ttk.Frame(main)
        footer.pack(fill=tk.X, pady=(12, 0))

        self.btn_back = ttk.Button(footer, text="Назад", command=self._cmd_back)
        self.btn_next = ttk.Button(footer, text="Далее", command=self._cmd_next)
        self.btn_next.pack(side=tk.RIGHT)
        self.btn_back.pack(side=tk.RIGHT, padx=(8, 0))

        self.f1 = ttk.Frame(self.container)
        self.f2 = ttk.Frame(self.container)
        self.f3 = ttk.Frame(self.container)
        self.f4 = ttk.Frame(self.container)
        self.f5 = ttk.Frame(self.container)
        for fr in (self.f1, self.f2, self.f3, self.f4, self.f5):
            fr.place(relwidth=1, relheight=1)

        self._preset_size_vars = {p: tk.StringVar(value="…") for p in PRESET_ORDER}
        self.preset_radio_var = tk.StringVar(value=CompressionPreset.WEAK.value)

        self._step = 1

        self._build_step_file(self.f1)
        self._build_step_preset(self.f2)
        self._build_step_extra(self.f3)
        self._build_step_format(self.f4)
        self._build_step_preview(self.f5)

        self._lift_step(1)

    def _component_status_lines(self) -> list[str]:
        lines = [f"Python {platform.python_version()} ({platform.system()})"]
        try:
            tk_patch = str(self.root.tk.call("info", "patchlevel"))
        except Exception:
            tk_patch = "?"
        lines.append(f"Tkinter · Tcl/Tk: доступен (patchlevel {tk_patch})")
        try:
            from PIL import __version__ as pil_ver  # type: ignore[import-untyped]

            lines.append(f"Pillow (PIL): {pil_ver}")
        except Exception:
            lines.append("Pillow (PIL): недоступен")
        lines.append(
            "tkinterdnd2 (drag-and-drop): "
            + ("установлен" if _HAS_DND else "не установлен — только «Открыть файл»")
        )
        return lines

    def _show_about_program(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("О Программе")
        dlg.transient(self.root)

        outer = ttk.Frame(dlg, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        body = (
            "Название\n"
            f"{APP_NAME_RU}\n\n"
            "Версия\n"
            f"{APP_VERSION}\n\n"
            "Описание\n"
            f"{APP_DESCRIPTION}\n\n"
            "Статус компонентов и наличие библиотек\n"
            + "\n".join(f"• {ln}" for ln in self._component_status_lines())
        )
        txt = tk.Text(
            outer,
            wrap=tk.WORD,
            width=62,
            height=18,
            bd=8,
            relief=tk.FLAT,
        )
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, body)
        txt.configure(state="disabled")

        btns = ttk.Frame(outer)
        btns.pack(pady=(12, 0))
        ttk.Button(btns, text="Закрыть", command=dlg.destroy).pack()

    def _show_about_developer(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("О Разработчике")
        dlg.transient(self.root)

        outer = ttk.Frame(dlg, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        row = ttk.Frame(outer)
        row.pack(anchor=tk.CENTER, pady=(0, 8))
        ttk.Label(row, text="Powered by").pack(side=tk.LEFT)

        link_lbl = tk.Label(
            row,
            text=REPOSITORY_URL,
            fg="#0066cc",
            cursor="hand2",
            font=("Segoe UI", 10, "underline"),
        )
        link_lbl.pack(side=tk.LEFT, padx=(6, 0))

        def open_repo(_evt: object = None) -> None:
            webbrowser.open(REPOSITORY_URL)

        link_lbl.bind("<Button-1>", open_repo)

        ttk.Label(outer, text="Лицензия MIT", justify=tk.CENTER).pack(pady=(4, 0))
        ttk.Label(outer, text="Свободное распространение.", justify=tk.CENTER).pack(
            pady=(4, 0),
        )
        ttk.Label(outer, text="2026", justify=tk.CENTER).pack(pady=(4, 0))

        ttk.Button(outer, text="Закрыть", command=dlg.destroy).pack(
            anchor=tk.CENTER,
            pady=(16, 0),
        )

    def _output_fmt(self) -> ip.OutputFormat:
        v = self._output_format_var.get()
        if v not in ("JPEG", "PNG", "WEBP", "BMP"):
            return "JPEG"
        return cast(ip.OutputFormat, v)

    def _preset_from_radio(self) -> CompressionPreset:
        return CompressionPreset(self.preset_radio_var.get())

    def _is_manual_compression(self) -> bool:
        return self.compression_mode_var.get() == "manual"

    def _manual_settings_from_ui(self) -> ManualCompressionSettings:
        if self.manual_no_resize.get():
            edge: int | None = None
        else:
            try:
                raw = str(self.manual_edge_var.get()).strip().replace(",", ".")
                edge = int(float(raw))
            except ValueError:
                edge = 2048
        return ManualCompressionSettings(
            max_long_edge=edge,
            jpeg_quality=int(self.manual_jpeg_val.get()),
            webp_quality=int(self.manual_webp_val.get()),
            png_compress_level=int(self.manual_png_val.get()),
        )

    def _compression_snapshot_preset_manual(
        self,
    ) -> tuple[CompressionPreset | None, ManualCompressionSettings | None]:
        if self._is_manual_compression():
            return None, clamp_manual(self._manual_settings_from_ui())
        return self._preset_from_radio(), None

    def _sync_manual_edge_widgets(self) -> None:
        off = tk.DISABLED if self.manual_no_resize.get() else tk.NORMAL
        if getattr(self, "manual_edge_spin", None) is not None:
            self.manual_edge_spin.configure(state=off)
        if self._step == 2:
            self._schedule_preset_estimates()

    def _on_compression_mode_changed(self) -> None:
        if getattr(self, "preset_rows_host", None) is None:
            return
        if self._is_manual_compression():
            self.preset_rows_host.pack_forget()
            self.manual_host.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            for b in getattr(self, "_preset_radio_widgets", []):
                b.configure(state=tk.DISABLED)
        else:
            self.manual_host.pack_forget()
            self.preset_rows_host.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            for b in getattr(self, "_preset_radio_widgets", []):
                b.configure(state=tk.NORMAL)
        self._schedule_preset_estimates()

    def _on_manual_any_change(self, *_args: object) -> None:
        m = clamp_manual(self._manual_settings_from_ui())
        if self.manual_jpeg_val.get() != m.jpeg_quality:
            self.manual_jpeg_val.set(m.jpeg_quality)
        if self.manual_webp_val.get() != m.webp_quality:
            self.manual_webp_val.set(m.webp_quality)
        if self.manual_png_val.get() != m.png_compress_level:
            self.manual_png_val.set(m.png_compress_level)
        if getattr(self, "lbl_manual_j", None) is not None:
            self.lbl_manual_j.configure(text=str(m.jpeg_quality))
            self.lbl_manual_w.configure(text=str(m.webp_quality))
            self.lbl_manual_p.configure(text=str(m.png_compress_level))
        if self._step == 2 and self._is_manual_compression():
            self._schedule_preset_estimates()

    def _lift_step(self, n: int) -> None:
        self._step = n
        titles = {
            1: "Шаг 1 из 5 · Файл",
            2: "Шаг 2 из 5 · Сила сжатия",
            3: "Шаг 3 из 5 · Дополнительные параметры",
            4: "Шаг 4 из 5 · Формат сохранения",
            5: "Шаг 5 из 5 · Предпросмотр и сохранение",
        }
        self.step_title.configure(text=titles[n])
        seq = (self.f1, self.f2, self.f3, self.f4, self.f5)
        for i, fr in enumerate(seq, start=1):
            if i == n:
                fr.lift()
            else:
                fr.lower()

        self.btn_back.configure(state=tk.DISABLED if n == 1 else tk.NORMAL)
        self.busy_banner.set("")

        if n == 5:
            self.btn_next.configure(text="Сжать", command=self._cmd_compress)
        else:
            self.btn_next.configure(text="Далее", command=self._cmd_next)

        if n == 2:
            self._schedule_preset_estimates()
        if n == 5:
            self._schedule_final_preview()

    def _cmd_back(self) -> None:
        if self._step <= 1:
            return
        self._lift_step(self._step - 1)

    def _cmd_next(self) -> None:
        step = self._step
        if step == 1:
            if not self.raw_path or self.pil_normalized is None:
                messagebox.showwarning(APP_TITLE, "Сначала выберите изображение.")
                return
        if step == 4:
            self._sync_filename_extension_with_format()
            if not self._alpha_dialog_if_needed():
                return
        if step >= 5:
            return
        self._lift_step(step + 1)

    def _build_step_file(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.BOTH, expand=True)
        row.columnconfigure(0, weight=3, minsize=320)
        row.columnconfigure(1, weight=2, minsize=260)
        row.rowconfigure(0, weight=1)

        left = tk.Frame(row, bd=2, relief=tk.GROOVE, padx=6, pady=6)
        left.grid(row=0, column=0, sticky=tk.NSEW)

        self.step1_preview = ResizingPreviewCanvas(left)
        self.step1_preview.pack(fill=tk.BOTH, expand=True)

        dz_line = (
            "Перетаскивание файла — сюда, на область предпросмотра."
            if _HAS_DND
            else ""
        )
        if dz_line:
            ttk.Label(left, text=dz_line, style="Muted.TLabel", wraplength=320).pack(
                anchor=tk.W,
                pady=(2, 0),
            )

        ttk.Button(left, text="Открыть файл…", command=self._browse_open).pack(
            fill=tk.X,
            pady=(10, 0),
        )

        if _HAS_DND:
            try:
                self.step1_preview.drop_target_register(DND_FILES)
                self.step1_preview.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

        self.step1_preview.clear_placeholder(self.step1_preview_hint)

        right = ttk.Frame(row, padding=(0, 0, 0, 0))
        right.grid(row=0, column=1, sticky=tk.NSEW, padx=(10, 0))

        ttk.Label(right, text="Сведения о файле:", style="Muted.TLabel").pack(anchor=tk.W)
        self.file_info_txt = tk.Text(right, wrap=tk.WORD, height=24, bd=8, relief=tk.FLAT)
        self.file_info_txt.pack(fill=tk.BOTH, expand=True)

    def _on_drop_files(self, event: object) -> None:
        raw = str(getattr(event, "data", ""))
        lst: list[str] = []
        try:
            lst = list(self.root.tk.splitlist(raw))
        except Exception:
            lst = []
        if not lst and raw:
            lst = [raw.strip().strip("{}")]
        first = lst[0] if lst else ""
        if first:
            self._try_open_path(first.strip("{}"))

    def _browse_open(self) -> None:
        fp = filedialog.askopenfilename(
            parent=self.root,
            title="Выберите изображение",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.jfif *.bmp *.webp"),
                ("Все файлы", "*.*"),
            ],
        )
        if fp:
            self._try_open_path(fp)

    def _write_file_info_locked(self, text: str) -> None:
        self.file_info_txt.configure(state="normal")
        self.file_info_txt.delete("1.0", tk.END)
        self.file_info_txt.insert(tk.END, text)
        self.file_info_txt.configure(state="disabled")

    def _try_open_path(self, path: str) -> None:
        path = os.path.abspath(path)
        try:
            im, sz = ip.load_source_image(path)
        except ip.UnsupportedAnimation as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        except ip.UnsupportedInputFormat as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        except OSError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return

        self.raw_path = path
        self.pil_normalized = im
        self.source_bytes_on_disk = sz

        w, h = im.size
        mode_txt = im.mode + (" + альфа" if ip.has_alpha(im) else "")
        ext_guess = os.path.splitext(path)[1][1:] or "?"

        exif_txt = ""
        brief = ip.brief_exif_lines(im)
        if brief:
            exif_txt = "EXIF (фрагмент):\n    " + "\n    ".join(brief)

        parts = [
            f"Путь:\n{path}",
            f"Размер на диске: {human_bytes(sz)}",
            f"Пиксели: {w} × {h}",
            f"Режим: {mode_txt}",
            f"Расширение: .{ext_guess.upper()}",
        ]
        if exif_txt:
            parts.append(exif_txt)
        self._write_file_info_locked("\n\n".join(parts))

        self.step1_preview.set_source_pil(im)

        stem = Path(path).stem
        self.out_filename.set(f"{stem}_compressed{fmt_to_ext(self._output_fmt())}")

    def _build_step_preset(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            style="Muted.TLabel",
            wraplength=880,
            justify=tk.LEFT,
            text=STEP2_HINT,
        ).pack(anchor="w", pady=(0, 10))

        mode_fr = ttk.Frame(parent)
        mode_fr.pack(anchor="w", pady=(0, 4))
        ttk.Radiobutton(
            mode_fr,
            variable=self.compression_mode_var,
            value="preset",
            text="Пресеты",
            command=self._on_compression_mode_changed,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            mode_fr,
            variable=self.compression_mode_var,
            value="manual",
            text="Вручную",
            command=self._on_compression_mode_changed,
        ).pack(side=tk.LEFT, padx=(20, 0))

        self.preset_rows_host = ttk.Frame(parent)
        self._preset_radio_widgets = []
        for preset in PRESET_ORDER:
            row = ttk.Frame(self.preset_rows_host)
            row.pack(anchor="w", pady=6)
            pr = preset_params(preset)
            rb = ttk.Radiobutton(
                row,
                variable=self.preset_radio_var,
                value=preset.value,
                text=pr.label_ru,
            )
            rb.pack(side=tk.LEFT)
            self._preset_radio_widgets.append(rb)
            ttk.Label(
                row,
                textvariable=self._preset_size_vars[preset],
                style="Muted.TLabel",
            ).pack(side=tk.LEFT, padx=(24, 0))

        self.manual_host = ttk.LabelFrame(parent, text="Размер и качество", padding=(10, 8))
        self.manual_host.columnconfigure(1, weight=1)

        self.lbl_manual_j = ttk.Label(self.manual_host, width=5)
        self.lbl_manual_w = ttk.Label(self.manual_host, width=5)
        self.lbl_manual_p = ttk.Label(self.manual_host, width=5)

        ttk.Checkbutton(
            self.manual_host,
            text="Не уменьшать размер (без изменения числа пикселей)",
            variable=self.manual_no_resize,
            command=self._sync_manual_edge_widgets,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(self.manual_host, text="Макс. длинная сторона (px):").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 4),
        )
        self.manual_edge_spin = ttk.Spinbox(
            self.manual_host,
            from_=MIN_LONG_EDGE_WHEN_LIMIT,
            to=MAX_LONG_EDGE,
            width=10,
            textvariable=self.manual_edge_var,
            command=self._on_manual_any_change,
        )
        self.manual_edge_spin.grid(row=1, column=1, sticky="w", pady=(8, 4))

        def add_scale(row: int, title: str, var: tk.IntVar, lo: int, hi: int, lbl: ttk.Label) -> None:
            ttk.Label(self.manual_host, text=title).grid(row=row, column=0, sticky="w", pady=4)
            sc = tk.Scale(
                self.manual_host,
                from_=lo,
                to=hi,
                orient=tk.HORIZONTAL,
                variable=var,
                length=300,
                showvalue=0,
                command=lambda _v=None: self._on_manual_any_change(),
            )
            sc.grid(row=row, column=1, sticky="ew", pady=4)
            lbl.grid(row=row, column=2, sticky="e", padx=(10, 0))

        add_scale(2, "JPEG качество (1–95):", self.manual_jpeg_val, 1, 95, self.lbl_manual_j)
        add_scale(3, "WebP качество (1–100):", self.manual_webp_val, 1, 100, self.lbl_manual_w)
        add_scale(4, "PNG сжатие (0–9):", self.manual_png_val, 0, 9, self.lbl_manual_p)

        ttk.Label(
            self.manual_host,
            style="Muted.TLabel",
            wraplength=520,
            justify=tk.LEFT,
            text="BMP: без настройки качества — только ресайз и подложка при прозрачности.",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 4))

        ttk.Label(self.manual_host, text="Оценка размера:").grid(
            row=6,
            column=0,
            sticky="w",
            pady=(4, 0),
        )
        ttk.Label(self.manual_host, textvariable=self.manual_estimate_var).grid(
            row=6,
            column=1,
            columnspan=2,
            sticky="w",
            pady=(4, 0),
        )

        self._on_manual_any_change()
        self._sync_manual_edge_widgets()
        self._on_compression_mode_changed()

    def _build_step_extra(self, parent: ttk.Frame) -> None:
        meta = ttk.LabelFrame(parent, text="Метаданные", padding=(10, 8))
        meta.pack(anchor="w", fill=tk.X, pady=(0, 12))

        ttk.Checkbutton(
            meta,
            text="Удалить метаданные из сохраняемого файла",
            variable=self.strip_meta,
        ).pack(anchor="w")

        ttk.Label(
            meta,
            style="Muted.TLabel",
            wraplength=820,
            justify=tk.LEFT,
            text=(
                "Убираются вложенные данные EXIF, IPTC, XMP (если были): дата съёмки, модель камеры, "
                "выдержка, GPS, комментарии кадра и т.п. Пиксели и прозрачность не меняются. "
                "Поворот по EXIF уже применён при открытии файла, картинка не «перевернётся» обратно. "
                "Размер файла может немного уменьшиться; удобно перед отправкой в мессенджер или в сеть."
            ),
        ).pack(anchor="w", pady=(6, 0))

        vis = ttk.LabelFrame(parent, text="Ресайз и сжатие", padding=(10, 8))
        vis.pack(anchor="w", fill=tk.X)

        ttk.Checkbutton(
            vis,
            text="Лучший ресайз и чуть более мягкое сжатие (LANCZOS +)",
            variable=self.optimize_visuals,
        ).pack(anchor="w")

        ttk.Label(
            vis,
            style="Muted.TLabel",
            wraplength=820,
            justify=tk.LEFT,
            text="Меньше «ступенек» при сильном уменьшении; файлы могут стать немного тяжелее при том же пресете.",
        ).pack(anchor="w", pady=(6, 0))

    def _build_step_format(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Файл сохранить как:", style="Muted.TLabel").pack(
            anchor="w",
            pady=(0, 8),
        )

        block = ttk.Frame(parent)
        block.pack(anchor="w")

        rows = [
            ("JPEG · по умолчанию (.jpg)", "JPEG"),
            ("PNG · сохраняет альфу", "PNG"),
            ("WebP · компактный формат (.webp)", "WEBP"),
            ("BMP · без сильного сжатия часто большой", "BMP"),
        ]
        for text, val in rows:
            rf = ttk.Frame(block)
            rf.pack(anchor="w", pady=4)
            ttk.Radiobutton(
                rf,
                variable=self._output_format_var,
                text=text,
                value=val,
            ).pack(side=tk.LEFT)

    def _build_step_preview(self, parent: ttk.Frame) -> None:
        sums = ttk.Frame(parent)
        sums.pack(fill=tk.X)
        self.lbl_sum_orig = ttk.Label(sums, text="", style="Muted.TLabel", wraplength=900)
        self.lbl_sum_orig.pack(anchor="w")
        self.lbl_sum_new = ttk.Label(sums, text="", wraplength=900)
        self.lbl_sum_new.pack(anchor="w", pady=(6, 0))

        canv = tk.Frame(parent)
        canv.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        lf = tk.Frame(canv, bd=1, relief=tk.GROOVE)
        rf = tk.Frame(canv, bd=1, relief=tk.GROOVE)
        lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        hint_prev = (
            "Колёсико мыши на области — масштаб; зажата левая кнопка — сдвиг (панорама)."
        )
        ttk.Label(lf, text="Оригинал").pack(pady=(4, 2))
        ttk.Label(lf, text=hint_prev, style="Muted.TLabel", wraplength=360).pack(
            anchor=tk.W,
            pady=(0, 2),
        )

        self.zp_orig = ZoomPanPreviewCanvas(lf)
        self.zp_orig.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ttk.Label(rf, text="Результат").pack(pady=(4, 2))
        ttk.Label(rf, text=hint_prev, style="Muted.TLabel", wraplength=360).pack(
            anchor=tk.W,
            pady=(0, 2),
        )

        self.zp_new = ZoomPanPreviewCanvas(rf)
        self.zp_new.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        bot = ttk.Frame(parent)
        bot.pack(fill=tk.X, pady=(14, 0))

        row1 = ttk.Frame(bot)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="Папка:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.out_folder, width=70).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            padx=(8, 8),
        )
        ttk.Button(row1, text="Обзор…", command=self._pick_out_dir).pack(side=tk.LEFT)

        row2 = ttk.Frame(bot)
        row2.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(row2, text="Имя файла:").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.out_filename, width=52).pack(
            side=tk.LEFT,
            fill=tk.X,
            padx=(8, 8),
            expand=False,
        )

    def _pick_out_dir(self) -> None:
        d = filedialog.askdirectory(parent=self.root, title="Папка для сохранения")
        if d:
            self.out_folder.set(os.path.abspath(d))

    def _sync_filename_extension_with_format(self) -> None:
        name = self.out_filename.get().strip()
        if not name:
            return
        stem, _ = os.path.splitext(name)
        if stem:
            self.out_filename.set(stem + fmt_to_ext(self._output_fmt()))

    def _alpha_dialog_if_needed(self) -> bool:
        if self._output_fmt() not in ("JPEG", "BMP"):
            return True
        if self.pil_normalized is None:
            return True
        if not ip.has_alpha(self.pil_normalized):
            return True

        dlg = tk.Toplevel(self.root)
        dlg.title(APP_TITLE + " · прозрачность")
        dlg.transient(self.root)
        dlg.grab_set()

        sel = tk.StringVar(value=self.alpha_bg if self.alpha_bg in ("white", "black") else "white")

        ttk.Label(
            dlg,
            text="JPEG и BMP не поддерживают прозрачность.\nВыберите цвет подложки:",
            justify=tk.CENTER,
            wraplength=420,
        ).pack(padx=16, pady=(16, 8))

        f = ttk.Frame(dlg)
        f.pack()
        ttk.Radiobutton(f, variable=sel, value="white", text="Белый").grid(
            row=0,
            column=0,
            padx=6,
        )
        ttk.Radiobutton(f, variable=sel, value="black", text="Чёрный").grid(
            row=0,
            column=1,
            padx=6,
        )

        cancelled = {"v": False}

        def ok() -> None:
            self.alpha_bg = sel.get()
            dlg.destroy()

        def cancel() -> None:
            cancelled["v"] = True
            dlg.destroy()

        rb = ttk.Frame(dlg)
        rb.pack(pady=16)
        ttk.Button(rb, text="Отмена", command=cancel).pack(side=tk.LEFT, padx=6)
        ttk.Button(rb, text="Продолжить", command=ok).pack(side=tk.LEFT, padx=6)

        dlg.wait_window()
        return not cancelled["v"]

    def _schedule_preset_estimates(self) -> None:
        if self.pil_normalized is None:
            return
        if self._estimate_running:
            return
        self._estimate_running = True
        self.busy_banner.set("Считаем оценки размеров…")

        fmt = self._output_fmt()
        snapshot = self.pil_normalized.copy()
        strip = self.strip_meta.get()
        optimize = self.optimize_visuals.get()
        bg = cast(pw.OpaqueBg, self.alpha_bg if self.alpha_bg in ("white", "black") else "white")

        manual_snap: ManualCompressionSettings | None = None
        if self._is_manual_compression():
            manual_snap = clamp_manual(self._manual_settings_from_ui())

        def work() -> None:
            err_msg: str | None = None
            sizes: dict[CompressionPreset, int] | None = None
            one_manual: int | None = None
            try:
                if manual_snap is not None:
                    one_manual = pw.estimate_manual_size(
                        snapshot,
                        manual=manual_snap,
                        fmt=fmt,
                        strip_metadata=strip,
                        optimize_visuals=optimize,
                        opaque_bg=bg,
                    )
                else:
                    sizes = pw.estimate_preset_sizes(
                        snapshot,
                        fmt=fmt,
                        strip_metadata=strip,
                        optimize_visuals=optimize,
                        opaque_bg=bg,
                    )
            except Exception as e:  # noqa: BLE001
                err_msg = str(e)

            def ui_done() -> None:
                self._estimate_running = False
                self.busy_banner.set("")
                if manual_snap is not None:
                    if err_msg or one_manual is None:
                        messagebox.showerror(
                            APP_TITLE,
                            f"Не удалось оценить размер: {err_msg or 'неизвестная ошибка'}",
                        )
                        return
                    self.manual_estimate_var.set(f"≈ {human_bytes(one_manual)}")
                    return
                if err_msg or sizes is None:
                    messagebox.showerror(
                        APP_TITLE,
                        f"Не удалось оценить пресеты: {err_msg or 'неизвестная ошибка'}",
                    )
                    return
                for preset, nbytes in sizes.items():
                    self._preset_size_vars[preset].set(f"≈ {human_bytes(nbytes)}")

            self.root.after(0, ui_done)

        threading.Thread(target=work, daemon=True).start()

    def _schedule_final_preview(self) -> None:
        if self.pil_normalized is None:
            return
        if self._preview_running:
            return
        self._preview_running = True
        self.busy_banner.set("Готовим предпросмотр…")

        self.zp_orig.clear()
        self.zp_new.clear()

        snap = self.pil_normalized.copy()
        preset_sp, manual_sp = self._compression_snapshot_preset_manual()
        strip = self.strip_meta.get()
        optimize = self.optimize_visuals.get()
        fmt_out = self._output_fmt()
        bg = cast(pw.OpaqueBg, self.alpha_bg if self.alpha_bg in ("white", "black") else "white")

        def work() -> None:
            payload: tuple[bytes, tuple[int, int]] | None = None
            left_p = None
            right_p = None
            err: str | None = None
            try:
                left_p, right_p = pw.make_preview_images(
                    snap,
                    preset=preset_sp,
                    manual=manual_sp,
                    strip_metadata=strip,
                    optimize_visuals=optimize,
                    fmt=fmt_out,
                    opaque_bg=bg,
                    edge=FINAL_PREVIEW_LONG_EDGE,
                )
                data, staged = pw.final_result_blob(
                    snap,
                    preset=preset_sp,
                    manual=manual_sp,
                    strip_metadata=strip,
                    optimize_visuals=optimize,
                    fmt=fmt_out,
                    opaque_bg=bg,
                )
                payload = (data, staged.size)
            except Exception as e:  # noqa: BLE001
                err = str(e)

            def ui_done() -> None:
                self._preview_running = False
                self.busy_banner.set("")
                if err or payload is None or left_p is None or right_p is None:
                    messagebox.showerror(
                        APP_TITLE,
                        f"Предпросмотр недоступен: {err or 'неизвестная ошибка'}",
                    )
                    return

                data, staged_size = payload
                self.zp_orig.set_source_pil_rgb(left_p)
                self.zp_new.set_source_pil_rgb(right_p)

                o = self.pil_normalized
                ow, oh = o.size if o else (0, 0)
                self.lbl_sum_orig.configure(
                    text=(
                        f"Оригинал: файл на диске {human_bytes(self.source_bytes_on_disk)}, "
                        f"{ow} × {oh} px"
                    ),
                )

                self.lbl_sum_new.configure(
                    text=(
                        f"Результат: оценка файла {human_bytes(len(data))}, "
                        f"{staged_size[0]} × {staged_size[1]} px, формат {fmt_out}"
                    ),
                )

                self._suggest_export_name()

            self.root.after(0, ui_done)

        threading.Thread(target=work, daemon=True).start()

    def _suggest_export_name(self) -> None:
        if self.raw_path and not self.out_filename.get().strip():
            stem = Path(self.raw_path).stem
            self.out_filename.set(f"{stem}_compressed{fmt_to_ext(self._output_fmt())}")

    def _cmd_compress(self) -> None:
        if self.pil_normalized is None or not self.raw_path:
            messagebox.showwarning(APP_TITLE, "Нет входного файла.")
            return
        fold = os.path.abspath(self.out_folder.get().strip())
        fn = self.out_filename.get().strip()
        if not fn:
            messagebox.showwarning(APP_TITLE, "Укажите имя файла.")
            return

        fmt = self._output_fmt()
        bg_arg: str | None
        if fmt in ("JPEG", "BMP"):
            bg_arg = self.alpha_bg if self.alpha_bg in ("white", "black") else "white"
        else:
            bg_arg = None

        out_path = os.path.join(fold, fn)

        if os.path.isdir(out_path):
            messagebox.showerror(APP_TITLE, "Указан путь, совпадающий с папкой. Задайте имя файла.")
            return

        if os.path.exists(out_path):
            if not messagebox.askyesno(APP_TITLE, "Файл уже существует. Перезаписать?"):
                return

        snap = self.pil_normalized.copy()
        preset_sp, manual_sp = self._compression_snapshot_preset_manual()
        strip = self.strip_meta.get()
        optimize = self.optimize_visuals.get()

        def work() -> None:
            err: str | None = None
            try:
                im_out = ip.apply_pipeline(
                    snap,
                    preset=preset_sp,
                    manual=manual_sp,
                    optimize_visuals=optimize,
                    strip_metadata=strip,
                )
                ip.save_to_disk(
                    im_out,
                    dest_path=out_path,
                    fmt=fmt,
                    preset=preset_sp,
                    manual=manual_sp,
                    strip_metadata=strip,
                    optimize_visuals=optimize,
                    alpha_background_if_needed=bg_arg,
                )
            except OSError as e:
                err = str(e)
            except Exception as e:  # noqa: BLE001
                err = f"Ошибка сохранения: {e}"

            self.root.after(0, lambda: self._after_save(err, out_path))

        threading.Thread(target=work, daemon=True).start()

    def _after_save(self, err: str | None, out_path: str) -> None:
        if err:
            messagebox.showerror(APP_TITLE, err)
        else:
            messagebox.showinfo(APP_TITLE, f"Готово.\n{out_path}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    CompressWizardApp().run()


if __name__ == "__main__":
    main()
