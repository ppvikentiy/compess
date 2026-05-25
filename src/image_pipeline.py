from __future__ import annotations



import os

from io import BytesIO

from typing import Literal, cast



from PIL import Image, ImageOps

from PIL.ExifTags import TAGS as EXIF_TAGS



from manual_settings import (

    ManualCompressionSettings,

    soften_manual_for_optimize_quality,

)

from presets import CompressionPreset, preset_params, soften_for_optimize_quality



OutputFormat = Literal["JPEG", "PNG", "WEBP", "BMP"]



Resampling = Image.Resampling



_ANIM_NOT_SUPPORTED_MSG = (

    "Анимированные изображения (GIF / анимированный WebP) не поддерживаются.\n"

    "Выберите обычный статичный файл."

)





class UnsupportedAnimation(ValueError):

    pass





class UnsupportedInputFormat(ValueError):

    pass





_ALLOWED_INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".jfif"}



SUPPORTED_EXTENSIONS_DESC = ", ".join(sorted(ext.lstrip(".").upper() for ext in _ALLOWED_INPUT_EXTENSIONS))





def brief_exif_lines(im: Image.Image, max_pairs: int = 6) -> list[str]:

    exif = im.getexif()

    if not exif:

        return []

    lines: list[str] = []

    for pid, val in list(exif.items())[:max_pairs]:

        tag = EXIF_TAGS.get(pid, pid)

        sval = val

        if isinstance(val, bytes):

            sval = f"<байты длиной {len(val)}>"

        text = str(sval).replace("\x00", " ").strip()

        if len(text) > 72:

            text = text[:69] + "..."

        lines.append(f"{tag}: {text}")

    return lines





def is_animated_gif(im: Image.Image) -> bool:

    fmt = im.format or ""

    if fmt.upper() != "GIF":

        return False

    try:

        return getattr(im, "n_frames", 1) > 1

    except Exception:

        return False





def is_animated_webp(im: Image.Image) -> bool:

    fmt = im.format or ""

    if fmt.upper() != "WEBP":

        return False

    try:

        if getattr(im, "is_animated", False):

            return True

        return getattr(im, "n_frames", 1) > 1

    except Exception:

        return False





def _raise_if_animation(im: Image.Image) -> None:

    if is_animated_gif(im) or is_animated_webp(im):

        raise UnsupportedAnimation(_ANIM_NOT_SUPPORTED_MSG)





def validate_input_path(path: str) -> None:

    _, ext = os.path.splitext(path)

    ext = ext.lower()

    if ext == ".gif":

        raise UnsupportedInputFormat(

            "Формат GIF не поддерживается. Используйте PNG или JPEG без анимации."

        )

    if ext and ext not in _ALLOWED_INPUT_EXTENSIONS:

        raise UnsupportedInputFormat(

            "Поддерживаются только файлы расширениями: "

            f"{SUPPORTED_EXTENSIONS_DESC}."

        )





def load_source_image(path: str) -> tuple[Image.Image, int]:

    validate_input_path(path)

    raw_size = os.path.getsize(path)

    try:

        im = Image.open(path)

        im.load()

    except Exception as exc:  # noqa: BLE001

        raise OSError(f"Не удалось открыть файл: {exc}") from exc

    fmt = im.format or ""

    if fmt.upper() == "GIF":

        raise UnsupportedAnimation(_ANIM_NOT_SUPPORTED_MSG)

    _raise_if_animation(im)



    allowed_fmt = {"", "PNG", "JPEG", "WEBP", "BMP"}

    key = fmt.upper()

    if key and key not in allowed_fmt:

        raise UnsupportedInputFormat(

            "Неподдерживаемый тип изображения внутри файла для этого приложения."

        )



    rgba = normalize_with_alpha(im.copy())

    return rgba, raw_size





def normalize_with_alpha(im: Image.Image) -> Image.Image:

    try:

        im = ImageOps.exif_transpose(im)

    except Exception:

        pass



    if im.mode == "RGBA":

        return im



    if im.mode == "LA":

        return im.convert("RGBA")



    if im.mode == "P":

        if "transparency" in im.info:

            return im.convert("RGBA")

        return im.convert("RGB")



    if im.mode == "RGB":

        return im



    if im.mode == "L":

        return im.convert("RGB")



    return im.convert("RGB")





def has_alpha(im: Image.Image) -> bool:

    return im.mode == "RGBA"





def strip_metadata_if_needed(im: Image.Image, strip: bool) -> Image.Image:

    if not strip:

        return im.copy()

    return Image.frombytes(im.mode, im.size, im.tobytes())





def resize_to_long_edge(im: Image.Image, max_long_edge: int | None, resampling: Resampling) -> Image.Image:

    if max_long_edge is None:

        return im.copy()

    w, h = im.size

    long_edge = max(w, h)

    if long_edge <= max_long_edge:

        return im.copy()

    scale = max_long_edge / float(long_edge)

    nw = max(1, int(round(w * scale)))

    nh = max(1, int(round(h * scale)))

    return im.resize((nw, nh), resampling)





def pick_resampling(optimize_visuals: bool) -> Resampling:

    return Resampling.LANCZOS if optimize_visuals else Resampling.BOX





def flatten_for_opaque_format(im: Image.Image, background: Literal["white", "black"]) -> Image.Image:

    bg = (255, 255, 255) if background == "white" else (0, 0, 0)

    if im.mode == "RGB":

        return im.copy()

    if im.mode != "RGBA":

        return im.convert("RGB")



    rgb = Image.new("RGB", im.size, bg)

    alpha = im.getchannel("A")

    rgb.paste(im, mask=alpha)

    return rgb





def _xor_preset_manual(

    preset: CompressionPreset | None,

    manual: ManualCompressionSettings | None,

) -> None:

    if (preset is None) == (manual is None):

        raise ValueError("Нужно передать preset или manual (ровно один вариант).")





def effective_max_long_edge(

    preset: CompressionPreset | None,

    manual: ManualCompressionSettings | None,

) -> int | None:

    _xor_preset_manual(preset, manual)

    if manual is not None:

        return manual.max_long_edge

    return preset_params(cast("CompressionPreset", preset)).max_long_edge





def apply_pipeline(

    im: Image.Image,

    *,

    preset: CompressionPreset | None = None,

    manual: ManualCompressionSettings | None = None,

    optimize_visuals: bool,

    strip_metadata: bool,

) -> Image.Image:

    _xor_preset_manual(preset, manual)

    im = strip_metadata_if_needed(im, strip_metadata)

    edge = effective_max_long_edge(preset, manual)

    resampling = pick_resampling(optimize_visuals)

    return resize_to_long_edge(im, edge, resampling)





def _coding_jpeg_webp_png_level(

    *,

    preset: CompressionPreset | None,

    manual: ManualCompressionSettings | None,

    optimize_visuals: bool,

) -> tuple[int | None, int | None, int]:

    _xor_preset_manual(preset, manual)

    if manual is not None:

        jq, wq = manual.jpeg_quality, manual.webp_quality

        png_level = manual.png_compress_level

        if optimize_visuals:

            jq, wq = soften_manual_for_optimize_quality(jq, wq)

        return jq, wq, png_level



    pc = cast("CompressionPreset", preset)

    pr = preset_params(pc)

    jq, wq = pr.jpeg_quality, pr.webp_quality

    if optimize_visuals:

        jq, wq = soften_for_optimize_quality(jq, wq, pc)

    return jq, wq, pr.png_compress_level





def encode_to_buffer(

    im: Image.Image,

    *,

    fmt: OutputFormat,

    preset: CompressionPreset | None = None,

    manual: ManualCompressionSettings | None = None,

    strip_metadata: bool,

    optimize_visuals: bool,

    opaque_background: Literal["white", "black"] = "white",

) -> bytes:

    _xor_preset_manual(preset, manual)

    im = strip_metadata_if_needed(im, strip_metadata)



    jq, wq, png_level = _coding_jpeg_webp_png_level(

        preset=preset,

        manual=manual,

        optimize_visuals=optimize_visuals,

    )



    bio = BytesIO()



    try:

        if fmt == "JPEG":

            rgb = flatten_for_opaque_format(im, opaque_background).convert("RGB")

            rgb.save(bio, format="JPEG", optimize=True, quality=int(jq or 82), progressive=True)

        elif fmt == "PNG":

            im.save(bio, format="PNG", optimize=True, compress_level=int(png_level))

        elif fmt == "WEBP":

            im.save(

                bio,

                format="WEBP",

                lossless=False,

                quality=int(wq or 80),

                method=6,

            )

        elif fmt == "BMP":

            flatten_for_opaque_format(im, opaque_background).convert("RGB").save(bio, format="BMP")

        else:

            raise ValueError(fmt)

    except Exception as exc:  # noqa: BLE001

        raise RuntimeError(f"Ошибка кодирования изображения: {exc}") from exc



    return bio.getvalue()





def save_to_disk(

    im_processed: Image.Image,

    *,

    dest_path: str,

    fmt: OutputFormat,

    preset: CompressionPreset | None = None,

    manual: ManualCompressionSettings | None = None,

    strip_metadata: bool,

    optimize_visuals: bool,

    alpha_background_if_needed: Literal["white", "black"] | None,

) -> int:

    bg = alpha_background_if_needed or "white"



    data = encode_to_buffer(

        im_processed,

        fmt=fmt,

        preset=preset,

        manual=manual,

        strip_metadata=strip_metadata,

        optimize_visuals=optimize_visuals,

        opaque_background=bg,

    )

    dirname = os.path.dirname(os.path.abspath(dest_path))

    os.makedirs(dirname, exist_ok=True)

    with open(dest_path, "wb") as fh:  # noqa: SIM115 simple save

        fh.write(data)

    return os.path.getsize(dest_path)





def thumbnail_for_preview(im: Image.Image, edge: int) -> Image.Image:

    im_rgb = ImageOps.contain(im, (edge, edge), method=Image.Resampling.LANCZOS)

    return im_rgb

