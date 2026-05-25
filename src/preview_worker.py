from __future__ import annotations

from typing import Literal

from PIL import Image

import image_pipeline as ip
from manual_settings import ManualCompressionSettings
from presets import CompressionPreset

OpaqueBg = Literal["white", "black"]


def estimate_preset_sizes(
    src: Image.Image,
    *,
    fmt: ip.OutputFormat,
    strip_metadata: bool,
    optimize_visuals: bool,
    opaque_bg: OpaqueBg = "white",
) -> dict[CompressionPreset, int]:
    sizes: dict[CompressionPreset, int] = {}
    for preset in CompressionPreset:
        staged = ip.apply_pipeline(
            src.copy(),
            preset=preset,
            manual=None,
            optimize_visuals=optimize_visuals,
            strip_metadata=strip_metadata,
        )
        blob = ip.encode_to_buffer(
            staged,
            fmt=fmt,
            preset=preset,
            manual=None,
            strip_metadata=strip_metadata,
            optimize_visuals=optimize_visuals,
            opaque_background=opaque_bg,
        )
        sizes[preset] = len(blob)
    return sizes


def estimate_manual_size(
    src: Image.Image,
    *,
    manual: ManualCompressionSettings,
    fmt: ip.OutputFormat,
    strip_metadata: bool,
    optimize_visuals: bool,
    opaque_bg: OpaqueBg = "white",
) -> int:
    staged = ip.apply_pipeline(
        src.copy(),
        preset=None,
        manual=manual,
        optimize_visuals=optimize_visuals,
        strip_metadata=strip_metadata,
    )
    blob = ip.encode_to_buffer(
        staged,
        fmt=fmt,
        preset=None,
        manual=manual,
        strip_metadata=strip_metadata,
        optimize_visuals=optimize_visuals,
        opaque_background=opaque_bg,
    )
    return len(blob)


def make_preview_images(
    src: Image.Image,
    *,
    preset: CompressionPreset | None = None,
    manual: ManualCompressionSettings | None = None,
    strip_metadata: bool,
    optimize_visuals: bool,
    fmt: ip.OutputFormat,
    opaque_bg: OpaqueBg,
    edge: int = 520,
) -> tuple[Image.Image, Image.Image]:
    staged = ip.apply_pipeline(
        src.copy(),
        preset=preset,
        manual=manual,
        optimize_visuals=optimize_visuals,
        strip_metadata=strip_metadata,
    )
    left = ip.thumbnail_for_preview(src.copy(), edge)
    if fmt in ("JPEG", "BMP"):
        right_src = ip.flatten_for_opaque_format(staged, opaque_bg)
    else:
        right_src = staged
    right = ip.thumbnail_for_preview(right_src, edge)
    return left, right


def final_result_blob(
    src: Image.Image,
    *,
    preset: CompressionPreset | None = None,
    manual: ManualCompressionSettings | None = None,
    strip_metadata: bool,
    optimize_visuals: bool,
    fmt: ip.OutputFormat,
    opaque_bg: OpaqueBg,
) -> tuple[bytes, Image.Image]:
    staged = ip.apply_pipeline(
        src.copy(),
        preset=preset,
        manual=manual,
        optimize_visuals=optimize_visuals,
        strip_metadata=strip_metadata,
    )
    data = ip.encode_to_buffer(
        staged,
        fmt=fmt,
        preset=preset,
        manual=manual,
        strip_metadata=strip_metadata,
        optimize_visuals=optimize_visuals,
        opaque_background=opaque_bg,
    )
    return data, staged
