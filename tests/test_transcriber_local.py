from pathlib import Path

import pytest

from extnded_thotz import transcriber
from extnded_thotz.audio_io import TARGET_RATE, load_wav_float32, resample_linear
from extnded_thotz.transcriber import (
    LocalWhisperBackend,
    TranscriptionError,
    make_backend,
)

FIXTURE = Path(__file__).parent / "fixtures" / "dictation.wav"


class _FakeModel:
    def __init__(self, name: str, broken: bool = False):
        self.name = name
        self.broken = broken
        self.calls = 0

    def transcribe(self, audio, **kwargs):
        from types import SimpleNamespace

        self.calls += 1
        if self.broken:
            raise RuntimeError("Invalid string length in model.bin")
        segment = SimpleNamespace(text="Hello world.", no_speech_prob=0.0, avg_logprob=0.0)
        return iter([segment]), None


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


def test_corrupt_cached_model_is_cleared_and_reloaded(tmp_path, monkeypatch):
    """A half-written model.bin used to break dictation until cleared by hand."""
    cache = tmp_path / "models--Systran--faster-whisper-base"
    cache.mkdir()
    (cache / "model.bin").write_bytes(b"truncated")
    monkeypatch.setattr(transcriber, "_model_cache_dir", lambda size: cache)

    backend = LocalWhisperBackend("base")
    attempts = []

    def fake_open():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Invalid string length in model.bin")
        return "loaded-model"

    monkeypatch.setattr(backend, "_open", fake_open)
    assert backend.load() is backend
    assert backend._model == "loaded-model"
    assert len(attempts) == 2
    assert not cache.exists()


def test_transcribe_rebuilds_model_that_breaks_mid_use(monkeypatch):
    """A cache rewritten under a loaded model must not break dictation forever."""
    import numpy as np

    backend = LocalWhisperBackend("base")
    backend._model = _FakeModel("stale", broken=True)
    rebuilt = _FakeModel("fresh")
    monkeypatch.setattr(backend, "_open", lambda: rebuilt)

    audio = np.full(TARGET_RATE, 0.1, dtype=np.float32)
    assert backend.transcribe(audio) == "Hello world."
    assert backend._model is rebuilt


def test_transcribe_gives_up_when_the_rebuilt_model_also_breaks(monkeypatch):
    import numpy as np

    backend = LocalWhisperBackend("base")
    backend._model = _FakeModel("stale", broken=True)
    rebuilt = _FakeModel("fresh", broken=True)
    monkeypatch.setattr(backend, "_open", lambda: rebuilt)

    with pytest.raises(TranscriptionError, match="Invalid string length"):
        backend.transcribe(np.full(TARGET_RATE, 0.1, dtype=np.float32))
    assert rebuilt.calls == 1  # one retry, not an endless rebuild loop


def test_model_load_failure_surfaces_as_transcription_error(tmp_path, monkeypatch):
    cache = tmp_path / "models--Systran--faster-whisper-base"
    cache.mkdir()
    monkeypatch.setattr(transcriber, "_model_cache_dir", lambda size: cache)

    backend = LocalWhisperBackend("base")

    def always_fails():
        raise RuntimeError("Invalid string length in model.bin")

    monkeypatch.setattr(backend, "_open", always_fails)
    with pytest.raises(TranscriptionError, match="Invalid string length"):
        backend.load()
    # the cache is cleared once, not on every later attempt
    assert not cache.exists()


def test_model_load_error_without_a_cache_is_not_retried(monkeypatch):
    monkeypatch.setattr(transcriber, "_model_cache_dir", lambda size: None)
    backend = LocalWhisperBackend("base")
    calls = []

    def fails():
        calls.append(1)
        raise RuntimeError("no such model")

    monkeypatch.setattr(backend, "_open", fails)
    with pytest.raises(TranscriptionError):
        backend.load()
    assert len(calls) == 1


def test_make_backend_selection():
    assert make_backend({"backend": "auto", "model_size": "base"}, api_key="").name == "local"
    assert make_backend({"backend": "auto", "openai_stt_model": "whisper-1"}, api_key="sk-x").name == "openai"
    assert make_backend({"backend": "local", "model_size": "base"}, api_key="sk-x").name == "local"
    assert make_backend({"backend": "openai", "openai_stt_model": "whisper-1"}, api_key="sk-x").name == "openai"
