from pathlib import Path

import pytest

from extnded_thotz.audio_io import TARGET_RATE, load_wav_float32, resample_linear
from extnded_thotz.transcriber import LocalWhisperBackend, make_backend

FIXTURE = Path(__file__).parent / "fixtures" / "dictation.wav"


def test_local_whisper_transcribes_tts_fixture():
    if not FIXTURE.exists():
        pytest.skip("fixture missing — run: python scripts/make_fixture.py")
    audio, rate = load_wav_float32(FIXTURE)
    audio = resample_linear(audio, rate, TARGET_RATE)
    text = LocalWhisperBackend("tiny").transcribe(audio).lower()
    hits = sum(word in text for word in ["hello", "world", "test", "dictation", "extended"])
    assert hits >= 3, f"transcript too far off: {text!r}"


def test_empty_audio_returns_empty_string():
    import numpy as np

    backend = LocalWhisperBackend("tiny")
    assert backend.transcribe(np.zeros(100, dtype=np.float32)) == ""


def test_silent_audio_never_hallucinates():
    """Dead air used to come back as Whisper's filler 'You'."""
    import numpy as np

    backend = LocalWhisperBackend("tiny")
    # long enough to pass the 0.1 s minimum, but below the silence gate:
    # must return "" without loading the model
    dead = np.full(TARGET_RATE * 2, 1e-5, dtype=np.float32)
    assert backend.transcribe(dead) == ""
    zeros = np.zeros(TARGET_RATE * 3, dtype=np.float32)
    assert backend.transcribe(zeros) == ""
    # corrupt driver buffer (broken WDM-KS endpoint) must never reach Whisper
    corrupt = np.full(TARGET_RATE * 2, 1e30, dtype=np.float32)
    assert backend.transcribe(corrupt) == ""
    nanbuf = np.full(TARGET_RATE * 2, np.nan, dtype=np.float32)
    assert backend.transcribe(nanbuf) == ""


def test_make_backend_selection():
    assert make_backend({"backend": "auto", "model_size": "base"}, api_key="").name == "local"
    assert make_backend({"backend": "auto", "openai_stt_model": "whisper-1"}, api_key="sk-x").name == "openai"
    assert make_backend({"backend": "local", "model_size": "base"}, api_key="sk-x").name == "local"
    assert make_backend({"backend": "openai", "openai_stt_model": "whisper-1"}, api_key="sk-x").name == "openai"
