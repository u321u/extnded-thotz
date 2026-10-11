# -*- mode: python ; coding: utf-8 -*-
# macOS PyInstaller spec: builds ExtndedThotz.app (unsigned).
# Run: python -m PyInstaller --noconfirm ExtndedThotz-mac.spec
# Requires macOS + pip install of requirements.txt on macOS.

import sys

block_cipher = None

a = Analysis(
    ["extnded_thotz/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/logo.png", "assets"),
    ],
    hiddenimports=[
        "pynput.keyboard",
        "pynput._util.darwin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_rth_ctranslate2.py"],
    excludes=["win32", "win32api", "win32con", "win32com", "pystray._win32"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ExtndedThotz",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="universal2",
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ExtndedThotz.app",
    icon=None,
    bundle_identifier="com.scoutgoat.extndedthotz",
    info_plist={
        "CFBundleName": "ExtndedThotz",
        "CFBundleDisplayName": "Extnded Thotz",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSMicrophoneUsageDescription":
            "Extnded Thotz listens while you hold the dictation hotkey so it can "
            "transcribe your speech locally. Audio is never uploaded anywhere.",
        "NSAppleEventsUsageDescription":
            "Extnded Thotz needs to send keystrokes (paste) to the app you are dictating into.",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
    },
)
