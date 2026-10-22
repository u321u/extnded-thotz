# -*- mode: python ; coding: utf-8 -*-
"""One-file Windows build.

Produces a self-contained `ExtndedThotz.exe` with no `_internal` folder beside
it, so the download works from any directory. `ExtndedThotz.spec` remains the
on-dir build used for local debugging.

The excludes below are packages that PyInstaller's static analysis drags in
through optional import paths (duckdb, botocore and matplotlib all arrive via
hooks from a dependency's optional extras) but that nothing in
`extnded_thotz/` imports. Removing them keeps the download under 120 MB.
"""

from PyInstaller.utils.hooks import collect_all

datas = [("assets", "assets")]
binaries = []
hiddenimports = []

for package in ("faster_whisper", "ctranslate2"):
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

EXCLUDES = [
    # optional heavy extras pulled in by dependency hooks, never imported here
    "duckdb",
    "botocore",
    "boto3",
    "s3transfer",
    "jmespath",
    "matplotlib",
    "contourpy",
    "cycler",
    "kiwisolver",
    "fontTools",
    "pyparsing",
    "pandas",
    "scipy",
    "pyarrow",
    # alternate inference backends; faster-whisper uses CTranslate2 only
    "onnxruntime",
    "torch",
    "tensorflow",
    "transformers",
    # dev and build tooling
    "pytest",
    "_pytest",
    "setuptools",
    "pip",
    "wheel",
    "IPython",
    "jupyter",
    "notebook",
    "rich",
    "pygments",
    "sphinx",
    "docutils",
    "pydoc_data",
    "test",
    # tkinter image/quick backends the app never selects
    "PIL.ImageQt",
    "PIL.ImageTk",
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ExtndedThotz",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/logo.png"],
)
