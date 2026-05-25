from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompressionPreset(Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    EXTREME = "extreme"


@dataclass(frozen=True)
class PresetParams:
    label_ru: str
    max_long_edge: int | None
    jpeg_quality: int
    webp_quality: int
    png_compress_level: int


def preset_params(p: CompressionPreset) -> PresetParams:
    if p == CompressionPreset.WEAK:
        return PresetParams(
            label_ru="Слабое",
            max_long_edge=8192,
            jpeg_quality=92,
            webp_quality=90,
            png_compress_level=3,
        )
    if p == CompressionPreset.MEDIUM:
        return PresetParams(
            label_ru="Среднее",
            max_long_edge=4096,
            jpeg_quality=82,
            webp_quality=78,
            png_compress_level=6,
        )
    if p == CompressionPreset.STRONG:
        return PresetParams(
            label_ru="Сильное",
            max_long_edge=2048,
            jpeg_quality=70,
            webp_quality=65,
            png_compress_level=8,
        )
    return PresetParams(
        label_ru="Экстремальное",
        max_long_edge=1280,
        jpeg_quality=55,
        webp_quality=50,
        png_compress_level=9,
    )


def soften_for_optimize_quality(
    jpeg_q: int, webp_q: int, preset: CompressionPreset
) -> tuple[int, int]:
    if preset == CompressionPreset.EXTREME:
        return min(95, jpeg_q + 6), min(100, webp_q + 8)
    if preset == CompressionPreset.STRONG:
        return min(95, jpeg_q + 4), min(100, webp_q + 6)
    if preset == CompressionPreset.MEDIUM:
        return min(95, jpeg_q + 3), min(100, webp_q + 4)
    return min(95, jpeg_q + 2), min(100, webp_q + 3)
