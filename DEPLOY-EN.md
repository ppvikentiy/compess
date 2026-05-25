# Install & build (“deploy”) guide

Install the runtime, run from source, and package **CompressWizard** into a portable folder containing `CompressWizard.exe`.

---

## Development / normal install

### 1. Python

Install [Python for Windows](https://www.python.org/downloads/) (**3.10+**). Enable **Add Python to PATH**.

Verify:

```powershell
python --version
pip --version
```

### 2. Project dependencies

From the repository root (`requirements.txt` should be here):

```powershell
cd path\to\compess
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

| Package | Purpose |
|---------|---------|
| `Pillow` | Image decoding/encoding pipeline |
| `tkinterdnd2` | File drag-and-drop on the preview (the app degrades cleanly if absent) |
| `PyInstaller` | Building the standalone bundle |

**tkinter** ships with official python.org builds; reinstall if `_tkinter` is missing.

### 3. Run

```powershell
python src\main.py
```

Or double-click `run_compress_wizard.bat`.

---

## Optional virtual environment

```powershell
cd path\to\compess
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src\main.py
```

Classic **cmd**:

```cmd
.\.venv\Scripts\activate.bat
```

---

## PyInstaller shipped build (no Python on end-user PCs)

Repository file `compress_app.spec` emits **`dist\CompressWizard\`** with `CompressWizard.exe` plus DLLs/data (GUI build, console disabled).

### Steps

```powershell
cd path\to\compess
pyinstaller compress_app.spec
```

or:

```powershell
python -m PyInstaller compress_app.spec
```

### Output

- Run `dist\CompressWizard\CompressWizard.exe`.
- **Distribute:** zip the entire `dist\CompressWizard\` folder. Recipients unpack and launch the executable—Python is **not** required on their machine.
- Unsigned EXEs may be flagged by Defender/SmartScreen; whitelist or adopt code signing under your policies.

### One-file exe

The bundled spec builds a **folder deployment** (`EXE` `exclude_binaries=True` plus `COLLECT`). Switch PyInstaller definitions if you insist on single-file redistribution and retest DLL/data paths afterward.

---

## Troubleshooting quick reference

| Symptom | Check |
|---------|-------|
| `python` unknown | PATH / reinstall with **Add Python to PATH** |
| `_tkinter` errors | Official installer with Tk bundled |
| No drag-drop | `pip install tkinterdnd2` |
| PyInstaller import errors | `pip install -r requirements.txt`; run PyInstaller next to `compress_app.spec` |

---

## Publishing the source repo to GitHub

The root [`.gitignore`](.gitignore) excludes virtual environments, PyInstaller `build/` and `dist/`, and other local artifacts.

After creating an empty GitHub repository (feel free to skip the auto-generated README if yours already exists locally):

```powershell
cd path\to\compess
git init
git branch -M main
git remote add origin https://github.com/USER/REPONAME.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

Pushes and pull requests to `main`/`master` run the [CI](.github/workflows/ci.yml) workflow: install dependencies from `requirements.txt` and byte-compile everything under `src/`.

---

Russian version: [DEPLOY](DEPLOY.md).
