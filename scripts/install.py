"""Install Extnded Thotz for the current user (no admin needed).

Copies the PyInstaller build to %LOCALAPPDATA%\\Programs\\ExtndedThotz and
creates Desktop + Start Menu shortcuts:
    python scripts/install.py [--startup]
"""

import argparse
import os
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
BUILD = PROJECT / "dist" / "ExtndedThotz"
APP_NAME = "Extnded Thotz"


def _shortcut(shell, folder: Path, target: Path, name: str = APP_NAME,
              arguments: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.lnk"
    lnk = shell.CreateShortcut(str(path))
    lnk.TargetPath = str(target)
    lnk.Arguments = arguments
    lnk.WorkingDirectory = str(target.parent)
    lnk.IconLocation = str(target)
    lnk.Description = f"{name} — hold a key, speak, get text"
    lnk.Save()
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--startup", action="store_true",
                        help="also create a Startup shortcut so it launches with Windows")
    args = parser.parse_args()

    import win32com.client

    if not (BUILD / "ExtndedThotz.exe").exists():
        raise SystemExit("Build first: python -m PyInstaller --noconfirm ExtndedThotz.spec")

    install_dir = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "ExtndedThotz"
    print(f"copying app to {install_dir} ...")
    shutil.copytree(BUILD, install_dir, dirs_exist_ok=True)
    exe = install_dir / "ExtndedThotz.exe"

    shell = win32com.client.Dispatch("WScript.Shell")
    desktop = Path(shell.SpecialFolders("Desktop"))
    programs = Path(shell.SpecialFolders("Programs"))
    print("shortcut:", _shortcut(shell, desktop, exe))
    print("shortcut:", _shortcut(shell, programs, exe))
    print("shortcut:", _shortcut(shell, desktop, exe, name="Thotz by Scout Goat",
                                 arguments="--profile scoutgoat"))
    print("shortcut:", _shortcut(shell, programs, exe, name="Thotz by Scout Goat",
                                 arguments="--profile scoutgoat"))
    if args.startup:
        print("shortcut:", _shortcut(shell, Path(shell.SpecialFolders("Startup")), exe))
    print("installed")


if __name__ == "__main__":
    main()
