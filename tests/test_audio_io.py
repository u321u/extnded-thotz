import io
import wave

import numpy as np

from extnded_thotz.audio_io import (
    TARGET_RATE,
    float32_to_wav_bytes,
    is_corrupt,
    is_silent,
    is_unusable,
    load_wav_float32,
    resample_linear,
    save_wav,
)


def _sine(seconds=0.5, rate=TARGET_RATE, hz=440.0):
    t = np.arange(int(seconds * rate)) / rate
    return (0.5 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def test_wav_bytes_header(tmp_path):
    data = float32_to_wav_bytes(_sine())
    with wave.open(io.BytesIO(data)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == TARGET_RATE


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "t.wav"
    original = _sine()
    save_wav(p, original)
    loaded, rate = load_wav_float32(p)
    assert rate == TARGET_RATE
    assert loaded.dtype == np.float32
    assert loaded.shape == original.shape
    assert np.allclose(loaded, original, atol=2 / 32768)


def test_stereo_downmixed(tmp_path):
    p = tmp_path / "s.wav"
    mono = _sine(0.1)
    stereo = np.stack([mono, mono], axis=1)
    ints = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(TARGET_RATE)
        w.writeframes(ints.tobytes())
    loaded, _ = load_wav_float32(p)
    assert loaded.ndim == 1
    assert np.allclose(loaded, mono, atol=2 / 32768)


def test_resample_changes_length():
    a = _sine(0.25, rate=8000)
    out = resample_linear(a, 8000, 16000)
    assert abs(out.size - a.size * 2) <= 2
    assert out.dtype == np.float32


def test_resample_noop_same_rate():
    a = _sine(0.1)
    assert resample_linear(a, TARGET_RATE, TARGET_RATE) is not None
    assert resample_linear(a, TARGET_RATE, TARGET_RATE).size == a.size


def test_is_silent_flags_dead_air():
    assert is_silent(np.zeros(TARGET_RATE, dtype=np.float32))
    assert is_silent(np.zeros(0, dtype=np.float32))
    # muted-mic floor observed in the field (~-80 dBFS)
    assert is_silent(np.full(TARGET_RATE, 1e-5, dtype=np.float32))


def test_is_silent_passes_real_signal():
    assert not is_silent(_sine())
    # ambient room floor in a normal room sits well above the gate
    assert not is_silent(np.full(TARGET_RATE, 5e-3, dtype=np.float32))


def test_is_corrupt_flags_garbage_buffers():
    # broken WDM-KS endpoints deliver float32 values like 1e30, not sound
    garbage = np.full(TARGET_RATE, 1e30, dtype=np.float32)
    assert is_corrupt(garbage)
    assert is_unusable(garbage)
    # ...and sometimes NaN, which defeats plain magnitude comparisons
    nanbuf = np.full(TARGET_RATE, np.nan, dtype=np.float32)
    assert is_corrupt(nanbuf)
    assert is_unusable(nanbuf)
    assert not is_corrupt(_sine())
    assert not is_corrupt(np.zeros(TARGET_RATE, dtype=np.float32))
    assert is_unusable(np.zeros(TARGET_RATE, dtype=np.float32))  # silent = unusable
    assert not is_unusable(_sine())
