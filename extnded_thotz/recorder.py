"""Microphone capture via sounddevice; always returns 16 kHz mono float32."""

import logging
import threading

import numpy as np

from .audio_io import TARGET_RATE, resample_linear

log = logging.getLogger("extnded_thotz")


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

    @staticmethod
    def input_device_available() -> bool:
        try:
            import sounddevice as sd

            return sd.query_devices(kind="input") is not None
        except Exception:
            return False

    def start(self) -> None:
        try:
            import sounddevice as sd
        except Exception as exc:
            raise MicUnavailableError(f"No microphone available: {exc}") from exc
        with self._lock:
            self._frames = []
            self._input_level = 0.0

        failures = []
        for device in self._input_candidates(sd):
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
        detail = failures[-1] if failures else "no input devices found"
        raise MicUnavailableError(f"Could not open microphone: {detail}")

    @staticmethod
    def _input_candidates(sd) -> list[int]:
        """Try the default input, then Windows hosts ordered by reliability."""
        devices = sd.query_devices()
        default = sd.default.device[0]
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
        return resample_linear(audio, self._rate or self.target_rate, self.target_rate)

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
