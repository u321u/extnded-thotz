"""DictationApp: hotkey → recorder → transcriber → cleanup → injector."""

import logging
import queue
import subprocess
import sys
import threading
import time

from . import config as config_mod
from . import llm_cleanup
from .audio_io import is_silent, is_unusable
from .cleanup import clean_transcript
from .history import History
from .hotkey import HotkeyController, KeyboardBinder
from .injector import _set_clipboard, inject_text
from .recorder import MicUnavailableError, Recorder
from .transcriber import TranscriptionError, make_backend

log = logging.getLogger("extnded_thotz")

MIN_AUDIO_SECONDS = 0.3


class DictationApp:
    def __init__(self, root, overlay, cfg):
        self.root = root
        self.overlay = overlay
        self.cfg = cfg
        self.enabled = True
        self.busy = False
        self.tray_icon = None
        self.last_text = ""
        self._ui_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._started_at = 0.0
        self._last_cfg_mtime = None
        self.recorder = Recorder()
        self.recorder.prefer_by_name(cfg.get("input_device", ""))
        self.api_key = config_mod.resolve_api_key(cfg)
        self.backend = make_backend(cfg, self.api_key)
        self.history = History(config_mod.config_dir() / "history.jsonl")
        self.controller = HotkeyController(
            self._hotkey_start, self._hotkey_stop, self._hotkey_cancel, mode=cfg["mode"]
        )
        self.binder = KeyboardBinder(self.controller, cfg["hotkey"])
        root.after(50, self._pump_ui)

    # -- UI marshaling (worker threads -> Tk main thread) --------------------
    def ui(self, fn) -> None:
        self._ui_queue.put(fn)

    def _pump_ui(self) -> None:
        try:
            while True:
                self._ui_queue.get_nowait()()
        except queue.Empty:
            pass
        if not self._stop_event.is_set():
            self.root.after(50, self._pump_ui)

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        self.binder.bind()
        if self.cfg.get("preload_model") and self.backend.name == "local":
            threading.Thread(target=self._preload, daemon=True, name="model-preload").start()
        # Find a mic that actually carries signal before the first dictation —
        # the Windows default can be muted/dead yet still open without error.
        self.recorder.schedule_probe()
        threading.Thread(target=self._watch_config, daemon=True, name="config-watch").start()
        log.info(
            "Extnded Thotz ready — %s '%s' to dictate (backend=%s, model=%s)",
            "hold" if self.cfg["mode"] == "hold" else "tap",
            self.cfg["hotkey"], self.backend.name, self.cfg.get("model_size"),
        )

    def quit(self) -> None:
        self._stop_event.set()
        try:
            self.binder.unbind()
        except Exception:
            pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)

    def _preload(self) -> None:
        try:
            self.backend.load()
            log.info("Local model '%s' loaded", self.cfg.get("model_size"))
        except Exception as exc:
            log.warning("Model preload failed: %s", exc)

    # -- hotkey callbacks (keyboard hook thread) -------------------------------
    def _hotkey_start(self) -> None:
        if not self.enabled or self.busy:
            return
        try:
            self.recorder.start()
        except MicUnavailableError as exc:
            log.error("%s", exc)
            self.ui(lambda: self.overlay.flash("✗ Mic unavailable"))
            return
        self._started_at = time.monotonic()
        self._set_tray_recording(True)
        if self.cfg.get("show_overlay", True):
            self.ui(lambda: self.overlay.listen(lambda: self.recorder.input_level))

    def _hotkey_stop(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        duration = time.monotonic() - self._started_at
        self._set_tray_recording(False)
        if audio.size < MIN_AUDIO_SECONDS * 16000:
            self.ui(lambda: self.overlay.flash("· too short"))
            return
        if is_unusable(audio):
            # Feeding silence/garbage to Whisper yields hallucinations ("You").
            silent = is_silent(audio)
            log.warning(
                "Capture unusable (%s) — skipping transcription",
                "silent" if silent else "corrupt",
            )
            message = "· mic silent — check mic" if silent else "· bad mic signal"
            self.ui(lambda: self.overlay.flash(message))
            self.recorder.schedule_probe()
            return
        self.busy = True
        if self.cfg.get("show_overlay", True):
            self.ui(lambda: self.overlay.show("… Transcribing", fg="#ffd75f"))
        threading.Thread(
            target=self._process, args=(audio, duration), daemon=True, name="dictation"
        ).start()

    def _hotkey_cancel(self) -> None:
        if not self.recorder.is_recording:
            return
        self.recorder.cancel()
        self._set_tray_recording(False)
        self.ui(lambda: self.overlay.flash("✕ Cancelled"))

    # -- pipeline (worker thread) ----------------------------------------------
    def _process(self, audio, duration) -> None:
        try:
            raw = self.backend.transcribe(audio, language=self.cfg.get("language") or None)
            text = clean_transcript(
                raw,
                remove_fillers_enabled=self.cfg.get("remove_fillers", True),
                voice_commands_enabled=self.cfg.get("voice_commands", True),
            )
            if text and llm_cleanup.should_polish(self.cfg, self.api_key):
                text = llm_cleanup.polish(
                    text, self.api_key, self.cfg.get("openai_llm_model", "gpt-4o-mini")
                )
            if not text:
                self.ui(lambda: self.overlay.flash("· nothing heard"))
                return
            if self.cfg.get("append_space"):
                text += " "
            inject_text(
                text,
                method=self.cfg.get("injection", "paste"),
                restore_clipboard=self.cfg.get("restore_clipboard", True),
            )
            self.last_text = text
            self.history.append(text, duration, self.backend.name)
            log.info("Injected %d chars (%.1fs audio, %s)", len(text), duration, self.backend.name)
            self.ui(self.overlay.hide)
        except TranscriptionError as exc:
            log.error("Transcription failed: %s", exc)
            self.ui(lambda: self.overlay.flash("✗ Transcription failed"))
        except Exception:
            log.exception("Dictation pipeline error")
            self.ui(lambda: self.overlay.flash("✗ Error — see log"))
        finally:
            self.busy = False

    # -- tray / settings --------------------------------------------------------
    def _set_tray_recording(self, recording: bool) -> None:
        icon = self.tray_icon
        if icon is None:
            return
        try:
            from .tray import load_logo_image

            icon.icon = load_logo_image(recording=recording)
        except Exception:
            pass

    def copy_last(self) -> None:
        if self.last_text:
            try:
                _set_clipboard(self.last_text)
            except Exception:
                pass

    def open_settings(self) -> None:
        if getattr(sys, "frozen", False):
            # PyInstaller build: sys.executable is ExtndedThotz.exe, which has no -m
            subprocess.Popen([sys.executable, "--settings"])
        else:
            subprocess.Popen([sys.executable, "-m", "extnded_thotz.settings_ui"])

    # -- config hot-reload -------------------------------------------------------
    def _watch_config(self) -> None:
        path = config_mod.config_path()
        while not self._stop_event.wait(2.0):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if self._last_cfg_mtime is None:
                self._last_cfg_mtime = mtime
                continue
            if mtime != self._last_cfg_mtime:
                self._last_cfg_mtime = mtime
                try:
                    self._reload_config()
                except Exception:
                    log.exception("Config reload failed")

    def _reload_config(self) -> None:
        old = self.cfg
        new = config_mod.load_config()
        self.cfg = new
        self.api_key = config_mod.resolve_api_key(new)
        backend_keys = ("backend", "model_size", "openai_stt_model")
        if any(new.get(k) != old.get(k) for k in backend_keys) or \
                config_mod.resolve_api_key(old) != self.api_key:
            self.backend = make_backend(new, self.api_key)
        self.controller.mode = new["mode"]
        if new["hotkey"] != old["hotkey"]:
            self.binder.rebind(new["hotkey"])
        if new.get("input_device", "") != old.get("input_device", ""):
            self.recorder.prefer_by_name(new.get("input_device", ""))
        log.info("Config reloaded (hotkey=%s, mode=%s, backend=%s)",
                 new["hotkey"], new["mode"], self.backend.name)
