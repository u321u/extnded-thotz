"""WAV helpers: 16 kHz mono float32 pipeline standard, 16-bit PCM on disk."""

import io
import wave
from pathlib import Path

import numpy as np

TARGET_RATE = 16000


def _float32_to_int16(audio: np.ndarray) -> np.ndarray:
    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)


def float32_to_wav_bytes(audio: np.ndarray, sample_rate: int = TARGET_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(_float32_to_int16(audio).tobytes())
    return buf.getvalue()


def save_wav(path, audio: np.ndarray, sample_rate: int = TARGET_RATE) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(float32_to_wav_bytes(audio, sample_rate))


def load_wav_float32(path):
    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"only 16-bit PCM WAV supported, got {width * 8}-bit")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio.astype(np.float32), rate


def resample_linear(audio: np.ndarray, src_rate: int, dst_rate: int = TARGET_RATE) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if src_rate == dst_rate or audio.size == 0:
        return audio
    n_out = int(round(audio.size * dst_rate / src_rate))
    positions = np.linspace(0, audio.size - 1, n_out)
    return np.interp(positions, np.arange(audio.size), audio).astype(np.float32)
