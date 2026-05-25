from __future__ import annotations

from dataclasses import dataclass

# Границы для ручного режима (пиксели длинной стороны)
MIN_LONG_EDGE_WHEN_LIMIT = 64
MAX_LONG_EDGE = 8192

JPEG_QUALITY_MIN = 1
JPEG_QUALITY_MAX = 95

WEBP_QUALITY_MIN = 1
WEBP_QUALITY_MAX = 100

PNG_COMPRESS_MIN = 0
PNG_COMPRESS_MAX = 9


@dataclass(frozen=True)
class ManualCompressionSettings:
    """Параметры сжатия в ручном режиме (max_long_edge None = без ресайза)."""

    max_long_edge: int | None
    jpeg_quality: int
    webp_quality: int
    png_compress_level: int


def clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def clamp_manual(m: ManualCompressionSettings) -> ManualCompressionSettings:
    jq = clamp_int(m.jpeg_quality, JPEG_QUALITY_MIN, JPEG_QUALITY_MAX)
    wq = clamp_int(m.webp_quality, WEBP_QUALITY_MIN, WEBP_QUALITY_MAX)
    png = clamp_int(m.png_compress_level, PNG_COMPRESS_MIN, PNG_COMPRESS_MAX)
    edge = m.max_long_edge
    if edge is not None:
        edge = clamp_int(edge, MIN_LONG_EDGE_WHEN_LIMIT, MAX_LONG_EDGE)
    return ManualCompressionSettings(
        max_long_edge=edge,
        jpeg_quality=jq,
        webp_quality=wq,
        png_compress_level=png,
    )


def soften_manual_for_optimize_quality(jpeg_q: int, webp_q: int) -> tuple[int, int]:
    """Фиксированное смягчение при «Оптимизировать качество» (уровень близко к «Среднее»)."""
    return min(JPEG_QUALITY_MAX, jpeg_q + 3), min(WEBP_QUALITY_MAX, webp_q + 4)
