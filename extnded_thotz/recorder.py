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
# Matched on word starts so "Microsoft Sound Mapper" is not taken for a mic.
VOICE_HINTS = ("microphone", "mic ", "mic(", "headset", "line in", "aux")

# A voice endpoint peaking this high is clearly live — no need to keep scanning.
STRONG_SIGNAL_PEAK = 0.02


class MicUnavailableError(RuntimeError):
    """No usable input device / device failed to open."""


def is_voice_name(name: str) -> bool:
    """True for names that look like a real microphone (not "Microsoft …")."""
    lowered = (name or "").lower().strip()
    if lowered.startswith("microsoft"):
        # "Microsoft Sound Mapper" / "Microsoft サウンド マッパー" are mixers,
        # not microphones — unless the rest of the name says microphone.
        return "microphone" in lowered or "mic " in lowered
    return any(hint in lowered for hint in VOICE_HINTS)


def is_dead_mapper(name: str) -> bool:
    """OS mixer endpoints: they open but never carry speech, and often hang."""
    lowered = (name or "").lower().strip()
    return (
        lowered.startswith("microsoft sound mapper")
        or lowered.startswith("primary sound capture driver")
    )


class Recorder:
    OPEN_TIMEOUT_S = 6.0
    # An endpoint can open without error yet never deliver a single frame
    # (muted mic). Wait this long for audio before moving on.
    FIRST_AUDIO_TIMEOUT_S = 1.0
    # Opening can block the whole interpreter (the driver holds the GIL), so
    # never keep probing after two endpoints that opened without audio: the
    # second is reported as "mic silent", which the user can act on.
    MAX_SILENT_DEVICES = 2
    # After a timeout, wait this long before touching the audio stack again
    # instead of writing the microphone off for the rest of the session.
    RETRY_COOLDOWN_S = 10.0

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
        self._wedged = False  # audio stack stopped answering during this session
        self._wedged_until = 0.0  # monotonic time before which we do not retry
        self._poisoned: set[int] = set()  # endpoints that hung; never retried
        self._opening_device = None  # candidate the opener thread is inside now
        self._open_abandoned = threading.Event()  # start() gave up; close late streams

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
        """Background-scan inputs and cache one that actually carries signal.

        Runs off the hotkey path; every device open inside it is watchdog-guarded
        so a dead endpoint is skipped instead of blocking the audio stack.
        """
        if self._probe_thread is not None and self._probe_thread.is_alive():
            return
        self._probe_stop.clear()
        self._probe_thread = threading.Thread(
            target=self.probe_working_device, daemon=True, name="mic-probe"
        )
        self._probe_thread.start()

    PROBE_SECONDS = 0.3
    PROBE_TIMEOUT_S = 1.5

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

    def _probe_capture_guarded(self, sd, device):
        """_probe_capture with a watchdog; None = no sample, hung or empty."""
        box: dict = {}

        def work():
            box["sample"] = self._probe_capture(sd, device)

        thread = threading.Thread(target=work, daemon=True, name="mic-probe-read")
        thread.start()
        thread.join(self.PROBE_TIMEOUT_S)
        if thread.is_alive():
            # Opening this endpoint blocks the audio driver; never touch it again.
            self._poisoned.add(device)
            log.warning("Microphone probe: device %s hung — skipping it", device)
            return None
        return box.get("sample")

    def probe_working_device(self, sd=None):
        """Scan candidates briefly; cache the best device that carries signal.

        Runs off the hotkey path. Every device open is watchdog-guarded: a hung
        endpoint is poisoned instead of blocking the audio stack for the session.
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
            if device in self._poisoned:
                continue
            sample = self._probe_capture_guarded(sd, device)
            if sample is None or is_unusable(sample):
                continue
            try:
                name = str(sd.query_devices(device)["name"])
            except Exception:
                name = ""
            pinned = bool(self._preferred_name) and self._preferred_name.lower() in name.lower()
            voice = is_voice_name(name)
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

    @staticmethod
    def _host_priority(host: str) -> int:
        priorities = {
            "Windows WDM-KS": 0,
            "Windows WASAPI": 1,
            "Windows DirectSound": 2,
            "MME": 3,
            "Core Audio": 0,
        }
        return priorities.get(host, 9)

    @staticmethod
    def _name_priority(name: str) -> int:
        lowered = (name or "").lower()
        if "microphone array" in lowered:
            return 0
        if "microphone" in lowered or "mic " in lowered or "headset" in lowered:
            return 1
        return 2

    def _ordered_candidates(self, sd) -> list[int]:
        """Pinned mic, then the mic that worked, then real mics, then the rest.

        Real microphone endpoints are ranked by host reliability before the OS
        default is considered: the default is often an MME "Sound Mapper" or a
        disabled/virtual array that blocks inside the driver, while the mic the
        user actually speaks into answers on WDM-KS. Loopback endpoints
        ("Stereo Mix", speaker "Input") come last — they carry system audio.
        """
        try:
            devices = sd.query_devices()
        except Exception:
            return []
        try:
            default = sd.default.device[0]
        except Exception:
            default = None

        def usable(index: int) -> bool:
            info = devices[index]
            return info["max_input_channels"] > 0 and not is_dead_mapper(info["name"])

        def rank(index: int):
            info = devices[index]
            try:
                host = sd.query_hostapis(info["hostapi"])["name"]
            except Exception:
                host = ""
            return (self._host_priority(host), self._name_priority(info["name"]), index)

        ordered: list[int] = []
        # 1. User-pinned name substring
        if self._preferred_name:
            needle = self._preferred_name.lower()
            ordered.extend(
                index
                for index, info in enumerate(devices)
                if usable(index) and needle in info["name"].lower()
            )
        # 2. Device that already produced usable audio this session — opening
        #    it is the fastest route back to a working dictation.
        if isinstance(self._preferred_device, int) and self._preferred_device not in ordered:
            ordered.append(self._preferred_device)
        # 3. Real microphones / headsets, best host first
        voice = [
            index
            for index, info in enumerate(devices)
            if usable(index)
            and index not in ordered
            and is_voice_name(info["name"])
        ]
        ordered.extend(sorted(voice, key=rank))
        # 4. OS default input device (may be a non-mic endpoint)
        if isinstance(default, int) and 0 <= default < len(devices) \
                and usable(default) and default not in ordered:
            ordered.append(default)
        # 5. Everything else, ordered by host reliability
        for index in self._input_candidates(sd):
            if index not in ordered:
                ordered.append(index)
        return ordered

    def start(self) -> None:
        try:
            import sounddevice as sd
        except Exception as exc:
            raise MicUnavailableError(f"No microphone available: {exc}") from exc
        if self._wedged:
            if time.monotonic() < self._wedged_until:
                raise MicUnavailableError(
                    "The microphone is still recovering — try again in a few seconds."
                )
            # Cooldown elapsed: give the audio stack another chance instead of
            # staying broken until the app is restarted.
            self._wedged = False
            self._wedged_until = 0.0
        # A running probe opens devices too; let it finish before we open one,
        # otherwise exclusive opens collide ("Device unavailable").
        self._probe_stop.set()
        probe = self._probe_thread
        if probe is not None and probe.is_alive():
            probe.join(timeout=0.4)
        with self._lock:
            self._frames = []
            self._input_level = 0.0
        self._open_abandoned.clear()

        # PortAudio opens call straight into the audio driver, and a wedged
        # endpoint (driver fault, a conflicting exclusive-mode app) blocks
        # inside the call with no error at all. Bound the wait so the hotkey
        # thread never freezes.
        box: dict = {}
        opener = threading.Thread(
            target=self._open_input, args=(sd, box), daemon=True, name="mic-open"
        )
        opener.start()
        # One extra second of slack: _open_input enforces its own deadline and
        # should get the chance to report which devices failed instead of the
        # whole session being declared wedged.
        opener.join(self.OPEN_TIMEOUT_S + 1.0)
        if opener.is_alive():
            self._open_abandoned.set()  # tell the late opener to close its stream
            self._wedged = True
            self._wedged_until = time.monotonic() + self.RETRY_COOLDOWN_S
            # Remember the endpoint that blocked so the next attempt after the
            # cooldown skips it instead of hanging on the same device forever.
            stuck = self._opening_device
            if stuck is not None:
                self._poisoned.add(stuck)
            log.error(
                "Microphone open did not return within %.0fs — the audio driver is wedged "
                "(device %s)", self.OPEN_TIMEOUT_S, stuck,
            )
            raise MicUnavailableError(
                "The microphone isn't responding. Another app may be holding it, or "
                "the audio driver is stuck — close other audio apps and try again."
            )
        if "error" in box:
            raise MicUnavailableError(f"Could not open microphone: {box['error']}")

    def _open_input(self, sd, box: dict) -> None:
        """Try candidate devices in order; store the working stream or the error.

        Runs in one bounded thread (see start()). Devices that hung in an earlier
        attempt are skipped, so each retry moves closer to a working endpoint.
        """
        failures = []
        silent_fallback = None  # endpoint that opened but carried nothing
        silent_count = 0
        for device in self._ordered_candidates(sd):
            if device in self._poisoned:
                failures.append(f"{device}: endpoint hung earlier this session")
                continue
            with self._lock:
                self._frames = []  # stale frames must not vouch for this device
            stream = None
            self._opening_device = device
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
                # Wait for the first callback: an endpoint that opens but stays
                # silent is dead, and recording from it yields nothing usable.
                wait_until = time.monotonic() + self.FIRST_AUDIO_TIMEOUT_S
                while time.monotonic() < wait_until:
                    with self._lock:
                        if self._frames:
                            break
                    time.sleep(0.02)
                with self._lock:
                    delivered = bool(self._frames)
                if not delivered:
                    failures.append(f"{device}: opened but delivered no audio")
                    silent_count += 1
                    if silent_fallback is not None:
                        try:
                            silent_fallback[1].stop()
                            silent_fallback[1].close()
                        except Exception:
                            pass
                    silent_fallback = (device, stream, rate)
                    if silent_count >= self.MAX_SILENT_DEVICES:
                        break  # stop scanning; report this endpoint as silent
                    continue
                # Keep only the winning stream open; drop any earlier silent one.
                if silent_fallback is not None:
                    try:
                        silent_fallback[1].stop()
                        silent_fallback[1].close()
                    except Exception:
                        pass
                if self._open_abandoned.is_set():
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    self._opening_device = None
                    return
                self._stream = stream
                self._rate = rate
                self._current_device = device
                self._opening_device = None
                host = sd.query_hostapis(info["hostapi"])["name"]
                log.info("Microphone opened: %s (%s, device %s)", info["name"], host, device)
                return
            except Exception as exc:
                self._opening_device = None
                failures.append(f"{device}: {exc}")
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
        if silent_fallback is not None:
            device, stream, rate = silent_fallback
            if self._open_abandoned.is_set():
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                self._opening_device = None
                return
            # Nothing carried audio (muted mic / no capture in this session).
            # Keep the endpoint so the app reports "mic silent" — actionable —
            # instead of pretending no microphone exists.
            self._stream = stream
            self._rate = rate
            self._current_device = device
            self._opening_device = None
            log.warning(
                "Microphone opened but carries no audio: device %s — keeping it as a fallback",
                device,
            )
            return
        self._stream = None
        box["error"] = failures[-1] if failures else "no input devices found"

    @classmethod
    def _input_candidates(cls, sd) -> list[int]:
        """Try the default input, then platform hosts ordered by reliability."""
        devices = sd.query_devices()
        default = sd.default.device[0]
        candidates = [
            (
                cls._name_priority(info["name"]),
                cls._host_priority(sd.query_hostapis(info["hostapi"])["name"]),
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
