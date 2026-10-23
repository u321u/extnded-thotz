"""Microphone capture via sounddevice; always returns 16 kHz mono float32."""

import logging
import threading
import time

import numpy as np

from .audio_io import TARGET_RATE, is_unusable, resample_linear

log = logging.getLogger("extnded_thotz")

# Name fragments that identify a real voice input. Auto-probe prefers these
# over loopback endpoints ("Stereo Mix", speaker "Input") that happily carry
# signal — but of system audio, which Whisper would happily transcribe.
VOICE_HINTS = ("mic", "headset", "line in", "aux")

# A voice endpoint peaking this high is clearly live — no need to keep scanning.
STRONG_SIGNAL_PEAK = 0.02


class MicUnavailableError(RuntimeError):
    """No usable input device / device failed to open."""


class Recorder:
    def __init__(self, target_rate: int = TARGET_RATE):
        self.target_rate = target_rate
        self._frames = []
        self._stream = None
        self._rate = None
        self._lock = threading.Lock()
        self._input_level = 0.0
        self._preferred_device = None  # cached index validated to carry signal
        self._preferred_name = ""      # user setting: mic name substring
        self._current_device = None
        self._probe_thread = None
        self._probe_stop = threading.Event()  # set by start() to abort a probe
        self._wedged = False  # audio driver stopped answering; stop opening

    @staticmethod
    def input_device_available() -> bool:
        try:
            import sounddevice as sd

            return sd.query_devices(kind="input") is not None
        except Exception:
            return False

    # -- microphone selection -------------------------------------------------

    def prefer_by_name(self, name: str) -> None:
        """Pin a microphone by name substring (config: input_device)."""
        self._preferred_name = (name or "").strip()

    def schedule_probe(self) -> None:
        """Background-scan inputs and cache one that actually carries signal."""
        if self._probe_thread is not None and self._probe_thread.is_alive():
            return
        self._probe_stop.clear()
        self._probe_thread = threading.Thread(
            target=self.probe_working_device, daemon=True, name="mic-probe"
        )
        self._probe_thread.start()

    PROBE_SECONDS = 0.3

    def _probe_capture(self, sd, device):
        """Grab ~PROBE_SECONDS of audio via the callback API.

        Blocking `stream.read()` raises "Blocking API not supported yet" on
        PortAudio's WDM-KS host — the most reliable Windows route, where the
        working mics live. The callback path works on every host.
        """
        chunks: list[np.ndarray] = []

        def _collect(indata, frames, time_info, status):
            chunks.append(indata.copy())

        try:
            info = sd.query_devices(device)
            rate = int(info["default_samplerate"] or self.target_rate)
            with sd.InputStream(
                device=device, samplerate=rate, channels=1,
                dtype="float32", callback=_collect,
            ):
                deadline = time.monotonic() + self.PROBE_SECONDS
                while time.monotonic() < deadline:
                    if self._probe_stop.is_set() or self.is_recording:
                        break
                    time.sleep(0.02)
        except Exception:
            return None
        if not chunks:
            return None
        return np.concatenate(chunks)[:, 0]

    def probe_working_device(self, sd=None):
        """Scan candidates briefly; cache the best device that carries signal.

        Runs off the hotkey path: a muted/blocked default mic (opens fine,
        delivers digital silence) is skipped instead of being used forever.

        Picks the loudest voice-named endpoint (mic/headset/line) over
        loopback ones, and re-probing after a dead capture happens while the
        user is usually still speaking — so the mic they actually use wins.
        """
        if sd is None:
            try:
                import sounddevice as sd
            except Exception:
                return None
        best = None  # (score tuple, peak, device)
        for device in self._ordered_candidates(sd):
            if self._probe_stop.is_set() or self.is_recording:
                return self._preferred_device
            sample = self._probe_capture(sd, device)
            if sample is None or is_unusable(sample):
                continue
            try:
                name = str(sd.query_devices(device)["name"])
            except Exception:
                name = ""
            lowered = name.lower()
            pinned = bool(self._preferred_name) and self._preferred_name.lower() in lowered
            voice = any(hint in lowered for hint in VOICE_HINTS)
            score = (int(pinned), int(voice))
            peak = float(np.max(np.abs(sample)))
            if best is None or score > best[0] or (score == best[0] and peak > best[1]):
                best = (score, peak, device)
            if pinned and voice:
                break  # user pinned this mic and it is alive — done
            if voice and peak >= STRONG_SIGNAL_PEAK:
                break  # clearly live voice endpoint — stop scanning
        if best is None:
            log.warning("Microphone probe: no input device carried signal")
            return None
        device = best[2]
        self._preferred_device = device
        log.info(
            "Microphone probe: %s (device %s) carries signal",
            sd.query_devices(device)["name"], device,
        )
        return device

    def _ordered_candidates(self, sd) -> list[int]:
        """Pinned name first, then probe result, then the default order."""
        devices = sd.query_devices()
        preferred: list[int] = []
        if self._preferred_name:
            needle = self._preferred_name.lower()
            preferred.extend(
                index
                for index, info in enumerate(devices)
                if info["max_input_channels"] > 0 and needle in info["name"].lower()
            )
        if (
            isinstance(self._preferred_device, int)
            and self._preferred_device not in preferred
        ):
            preferred.append(self._preferred_device)
        rest = [i for i in self._input_candidates(sd) if i not in preferred]
        return preferred + rest

    OPEN_TIMEOUT_S = 6.0

    def start(self) -> None:
        try:
            import sounddevice as sd
        except Exception as exc:
            raise MicUnavailableError(f"No microphone available: {exc}") from exc
        if self._wedged:
            raise MicUnavailableError(
                "The microphone stopped responding — restart the audio device or reboot."
            )
        # A running probe opens devices too; let it finish before we open one,
        # otherwise exclusive WDM-KS opens collide ("Device unavailable") and
        # the probe's in-flight read could outlast our recording attempt.
        self._probe_stop.set()
        probe = self._probe_thread
        if probe is not None and probe.is_alive():
            probe.join(timeout=0.6)
        with self._lock:
            self._frames = []
            self._input_level = 0.0

        # PortAudio opens call straight into the audio driver, and a wedged
        # endpoint (driver fault, a conflicting exclusive-mode app) blocks
        # inside the call with no error at all. That froze the hotkey thread,
        # so the app looked dead: no overlay, no text, no log line. Bound the
        # wait and give up on audio for this session instead — stacking more
        # opens behind a stuck driver can take the whole process down.
        box: dict = {}
        opener = threading.Thread(
            target=self._open_input, args=(sd, box), daemon=True, name="mic-open"
        )
        opener.start()
        opener.join(self.OPEN_TIMEOUT_S)
        if opener.is_alive():
            self._wedged = True
            log.error(
                "Microphone open did not return within %.0fs — the audio driver is wedged",
                self.OPEN_TIMEOUT_S,
            )
            raise MicUnavailableError(
                "The microphone isn't responding. Another app may be holding it, or "
                "the audio driver is stuck — a reboot clears it."
            )
        if "error" in box:
            raise MicUnavailableError(f"Could not open microphone: {box['error']}")

    def _open_input(self, sd, box: dict) -> None:
        """Try each candidate device; store the working stream or the last error."""
        failures = []
        for device in self._ordered_candidates(sd):
            stream = None
            try:
                info = sd.query_devices(device)
                rate = int(info["default_samplerate"] or self.target_rate)
                stream = sd.InputStream(
                    device=device,
                    samplerate=rate,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                )
                stream.start()
                self._stream = stream
                self._rate = rate
                self._current_device = device
                host = sd.query_hostapis(info["hostapi"])["name"]
                log.info("Microphone opened: %s (%s, device %s)", info["name"], host, device)
                return
            except Exception as exc:
                failures.append(f"{device}: {exc}")
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
        self._stream = None
        box["error"] = failures[-1] if failures else "no input devices found"

    @staticmethod
    def _input_candidates(sd) -> list[int]:
        """Try the default input, then platform hosts ordered by reliability."""
        import sys

        devices = sd.query_devices()
        default = sd.default.device[0]
        if sys.platform == "darwin":
            priorities = {
                "Core Audio": 0,
            }
        else:
            priorities = {
                "Windows WDM-KS": 0,
                "Windows WASAPI": 1,
                "Windows DirectSound": 2,
                "MME": 3,
            }
        def name_priority(name: str) -> int:
            lowered = name.lower()
            if "microphone array" in lowered:
                return 0
            if "microphone" in lowered or "mic " in lowered or "headset" in lowered:
                return 1
            return 2

        candidates = [
            (
                name_priority(info["name"]),
                priorities.get(sd.query_hostapis(info["hostapi"])["name"], 9),
                index,
            )
            for index, info in enumerate(devices)
            if info["max_input_channels"] > 0 and index != default
        ]
        candidates.sort()
        default_first = [default] if isinstance(default, int) and default >= 0 else []
        return default_first + [index for _name_priority, _host_priority, index in candidates]

    def _callback(self, indata, frames, time_info, status) -> None:
        with self._lock:
            self._frames.append(indata.copy())
            rms = float(np.sqrt(np.mean(np.square(indata, dtype=np.float64))))
            self._input_level = min(1.0, rms * 12.0)

    def stop(self) -> np.ndarray:
        audio = self._collect()
        if audio.size and not is_unusable(audio) and self._current_device is not None:
            self._preferred_device = self._current_device  # confirmed working — keep it
        audio = resample_linear(audio, self._rate or self.target_rate, self.target_rate)
        if not audio.size:
            log.warning("Capture produced no audio frames")
            return audio
        peak = float(np.max(np.abs(audio)))
        log.info(
            "Captured %.2fs (peak %.5f = %.1f dBFS)",
            audio.size / self.target_rate, peak,
            20.0 * float(np.log10(peak)) if peak > 0 else -120.0,
        )
        return audio

    def cancel(self) -> None:
        self._collect()

    def _collect(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._lock:
            frames, self._frames = self._frames, []
            self._input_level = 0.0
        if not frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(frames)[:, 0]

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def input_level(self) -> float:
        with self._lock:
            return self._input_level
