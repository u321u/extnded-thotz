"""Microphone capture via sounddevice; always returns 16 kHz mono float32."""

import threading

import numpy as np

from .audio_io import TARGET_RATE, resample_linear


class MicUnavailableError(RuntimeError):
    """No usable input device / device failed to open."""


class Recorder:
    def __init__(self, target_rate: int = TARGET_RATE):
        self.target_rate = target_rate
        self._frames = []
        self._stream = None
        self._rate = None
        self._lock = threading.Lock()

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

            info = sd.query_devices(kind="input")
            rate = int(info["default_samplerate"] or self.target_rate)
        except Exception as exc:
            raise MicUnavailableError(f"No microphone available: {exc}") from exc
        with self._lock:
            self._frames = []
        try:
            self._stream = sd.InputStream(
                samplerate=rate, channels=1, dtype="float32", callback=self._callback
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise MicUnavailableError(f"Could not open microphone: {exc}") from exc
        self._rate = rate

    def _callback(self, indata, frames, time_info, status) -> None:
        with self._lock:
            self._frames.append(indata.copy())

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
        if not frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(frames)[:, 0]

    @property
    def is_recording(self) -> bool:
        return self._stream is not None
