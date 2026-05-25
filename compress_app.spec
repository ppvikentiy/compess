# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas: list[tuple[str, str]] = []
binaries: list[tuple[str, str, str]] = []
hiddenimports: list[str] = []

for pkg in ("PIL", "tkinterdnd2"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas.extend(d)
    binaries.extend(b)
    hiddenimports.extend(h)

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy",
        "matplotlib",
        "pandas",
        "scipy",
        "cv2",
        "IPython",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CompressWizard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CompressWizard",
)
