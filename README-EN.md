# Image Compression Wizard

**Русский:** [README.md](README.md)

A **Python 3** desktop app for Windows with a **Tkinter** UI. It walks you through reducing the file size and resolution of a single static image and exporting it to the format you choose. Everything runs **locally**; no internet is required.

## Features

- **Five-step wizard** — image → compression strength → extra options → output format → preview and save.
- **Supported inputs:** PNG, JPEG/JFIF, BMP, WebP (single frame only). **Not supported:** GIF and animated WebP.
- **On open:** automatic EXIF orientation (`ImageOps.exif_transpose`), file metadata (disk size, pixel dimensions, color mode, alpha, a short EXIF excerpt when present).
- **Compression step:**
  - **Presets:** Weak, Medium, Strong, Extreme — each combines a maximum long-edge size in pixels with JPEG/WebP quality and PNG compression level.
  - **Manual:** set max long edge (or “no resize”), separate sliders for JPEG quality, WebP quality, and PNG `compress_level`, plus an **estimated output size** for the format selected at step 4.
- **Extra options:**
  - strip metadata from the saved file (EXIF, IPTC, XMP, etc.) — metadata only; pixels unchanged;
  - “Better resize and slightly softer compression” — use LANCZOS instead of BOX and bump JPEG/WebP quality a bit when saving (output may be slightly larger).
- **Output formats:** JPEG (`.jpg`), PNG (preserves alpha), WebP (lossy), BMP (typically large without heavy compression; alpha flattened onto a matte).
- **Alpha with JPEG/BMP:** dialog to pick white or black as the matte background.
- **Preview step:** side-by-side “Original” and “Result”; mouse wheel zoom, left-drag to pan; size summary; output folder and filename; overwrite confirmation when the file exists.

## Requirements

- Windows 10/11 (primary target environment).
- **Python 3.10+** is recommended.

## Dependencies

From `requirements.txt`:

- **Pillow** — I/O, EXIF, resize, codecs.
- **tkinterdnd2** — drag-and-drop onto the preview (step 1). Without it the app still runs; only drag-and-drop is unavailable.
- **PyInstaller** — used only when building an executable bundle (see [DEPLOY-EN](DEPLOY-EN.md)).

Python’s bundled **tkinter** is required for the GUI.

## Install and run from source

See [DEPLOY-EN](DEPLOY-EN.md) for deeper setup/build notes.

Short version:

1. Install [Python](https://www.python.org/downloads/) for Windows and enable **Add Python to PATH**.
2. In the project directory:
   ```text
   python -m pip install -r requirements.txt
   ```
3. Start the app:

   **Batch file (repository root):**

   ```text
   run_compress_wizard.bat
   ```

   **Or directly:**

   ```text
   python src\main.py
   ```

## How to use

1. **Step 1 — File**  
   Use “Open file…” or drag an image onto the preview (when `tkinterdnd2` is installed).

2. **Step 2 — Strength**  
   Pick **Presets** and one level; estimated file sizes appear for each preset (respecting step 3 options and the format set at step 4). Or choose **Manual**, adjust long edge / no resize, move the quality sliders, and read **Size estimate**.

3. **Step 3 — Extra**  
   Optionally enable metadata stripping and/or the higher-quality resize/compression mode (see inline hints).

4. **Step 4 — Format**  
   Choose JPEG, PNG, WebP, or BMP. The default filename extension is aligned when you continue. Transparent sources with JPEG/BMP trigger a matte color choice.

5. **Step 5 — Preview & save**  
   Wait for the preview to finish, compare Original vs Result, set **Folder** and **Filename**, then press **Compress**. On success you get the saved path.

Unsupported or animated inputs show a clear error message.

## Executable build and deployment

See [DEPLOY-EN](DEPLOY-EN.md).

## License

MIT — see [LICENSE](LICENSE).
