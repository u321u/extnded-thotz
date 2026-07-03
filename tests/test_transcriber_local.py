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


def test_make_backend_selection():
    assert make_backend({"backend": "auto", "model_size": "base"}, api_key="").name == "local"
    assert make_backend({"backend": "auto", "openai_stt_model": "whisper-1"}, api_key="sk-x").name == "openai"
    assert make_backend({"backend": "local", "model_size": "base"}, api_key="sk-x").name == "local"
    assert make_backend({"backend": "openai", "openai_stt_model": "whisper-1"}, api_key="sk-x").name == "openai"
