"""Entry point: python -m extnded_thotz [--smoke SECONDS] [--once WAV]"""

import argparse
import logging
import logging.handlers
import os
import socket
import sys
import zlib

from . import APP_DISPLAY_NAME, config as config_mod

SINGLETON_PORT = 48653


def _setup_logging():
    log_dir = config_mod.config_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def _singleton_port() -> int:
    profile = os.environ.get("EXTNDED_THOTZ_PROFILE", "").strip()
    if not profile:
        return SINGLETON_PORT
    return SINGLETON_PORT + 1 + (zlib.crc32(profile.encode("utf-8")) % 1000)


def _single_instance_guard():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", _singleton_port()))
        return sock
    except OSError:
        sock.close()
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="extnded-thotz", description=APP_DISPLAY_NAME)
    parser.add_argument("--smoke", type=float, default=0,
                        help="run for N seconds then exit cleanly (self-test)")
    parser.add_argument("--once", metavar="WAV",
                        help="transcribe a WAV file and print the text (no GUI)")
    parser.add_argument("--settings", action="store_true",
                        help="open the settings window instead of the tray app")
    parser.add_argument("--profile", default="",
                        help="named settings profile — own config, history, and instance lock")
    args = parser.parse_args(argv)

    if args.profile:
        # Everything (config dir, history, log, singleton port, child processes)
        # derives from this env var, so set it before anything reads config.
        os.environ["EXTNDED_THOTZ_PROFILE"] = args.profile.strip()

    if args.settings:
        from .settings_ui import main as settings_main

        settings_main()
        return 0

    _setup_logging()
    log = logging.getLogger("extnded_thotz")

    if args.once:
        from .transcriber import _main as transcribe_main

        return transcribe_main([args.once])

    guard = _single_instance_guard()
    if guard is None:
        message = (
            f"{APP_DISPLAY_NAME} is already running.\n\n"
            "Look for the goat icon in the system tray / menu bar — it may "
            "be hidden behind the overflow arrow near the clock."
        )
        print(message)
        if sys.platform == "win32":
            try:
                # Windowed (pyinstaller --noconsole) builds have no stdout, so a
                # silent exit here looks like "the app won't open" — show a dialog.
                import ctypes

                ctypes.windll.user32.MessageBoxW(None, message, APP_DISPLAY_NAME, 0x40)
            except Exception:
                pass
        else:
            try:
                import tkinter as tk
                from tkinter import messagebox

                _root = tk.Tk(); _root.withdraw()
                messagebox.showinfo(APP_DISPLAY_NAME, message, parent=_root)
                _root.destroy()
            except Exception:
                pass
        return 1

    import tkinter as tk

    from .app import DictationApp
    from .overlay import Overlay
    from .tray import build_tray

    cfg = config_mod.load_config()
    config_mod.save_config(cfg)  # materialize defaults on first run

    root = tk.Tk()
    root.withdraw()
    root.title(APP_DISPLAY_NAME)
    overlay = Overlay(root)
    app = DictationApp(root, overlay, cfg)
    try:
        icon = build_tray(app)
        app.tray_icon = icon
        icon.run_detached()
    except Exception as exc:
        log.warning("Tray unavailable, continuing without it: %s", exc)
    app.start()
    log.info("ready")
    if args.smoke:
        root.after(int(args.smoke * 1000), app.quit)
    root.mainloop()
    guard.close()
    # PortAudio teardown can block forever when a microphone open was abandoned
    # inside a wedged driver, leaving the app's process alive after quit.
    sys.stdout.flush()
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
