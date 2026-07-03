"""Create a Desktop shortcut to the packaged ExtndedThotz.exe (dev-only).

Run after a PyInstaller build:
    python scripts/make_shortcut.py
"""

from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
EXE = PROJECT / "dist" / "ExtndedThotz" / "ExtndedThotz.exe"


def main() -> None:
    import win32com.client

    if not EXE.exists():
        raise SystemExit(f"Build the app first — missing {EXE}")
    shell = win32com.client.Dispatch("WScript.Shell")
    desktop = Path(shell.SpecialFolders("Desktop"))
    shortcut = shell.CreateShortcut(str(desktop / "Extnded Thotz.lnk"))
    shortcut.TargetPath = str(EXE)
    shortcut.WorkingDirectory = str(EXE.parent)
    shortcut.IconLocation = str(EXE)
    shortcut.Description = "Extnded Thotz — hold a key, speak, get text"
    shortcut.Save()
    print(f"created {desktop / 'Extnded Thotz.lnk'}")


if __name__ == "__main__":
    main()
