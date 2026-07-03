# Extnded Thotz — Voice Dictation App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Windows voice-dictation app in the style of Wispr Flow: hold a hotkey anywhere, speak, release — polished text is typed into whatever app has focus.

**Architecture:** A Python tray app. A global hotkey (via `keyboard`) drives a push-to-talk state machine → microphone capture (`sounddevice`) → local offline speech-to-text (`faster-whisper`, with optional OpenAI cloud backends) → rule-based cleanup (fillers, voice commands, punctuation spacing, capitalization) plus optional LLM polish → clipboard-paste injection into the focused window (clipboard restored afterward). Tk main thread owns a floating status pill; pystray runs detached; transcription runs on worker threads.

**Tech Stack:** Python 3.14, faster-whisper (CTranslate2, CPU int8), sounddevice, keyboard, pystray + Pillow, pyperclip, tkinter, openai (optional), pytest. Windows-first.

**Independent implementation note:** This is an original implementation inspired by the *product category* Wispr Flow popularized. No Wispr Flow code, assets, branding, or name is used. Branding is the user's own "Extnded Thotz" name and goat logo (`assets/logo.png`).

## Global Constraints

- Python 3.14 / Windows 11. All native deps verified to have cp314 wheels: ctranslate2 4.8.0, faster-whisper 1.2.1, sounddevice 0.5.5, pywin32 312.
- **Must work fully offline with no API key** (no `OPENAI_API_KEY` on this machine). OpenAI STT/LLM paths are optional and config-gated.
- App/package naming: display name `Extnded Thotz`, Python package `extnded_thotz`, config dir `%APPDATA%\ExtndedThotz`.
- Audio pipeline standard: 16 kHz mono float32 (`TARGET_RATE = 16000` in `audio_io.py`).
- No admin rights assumed. No global state left behind on exit (keyboard hooks unbound, tray icon stopped).
- Tk API calls only from the main thread (worker threads marshal via the app's UI queue).
- Tests must run without a human speaking: STT end-to-end test uses a Windows SAPI text-to-speech fixture WAV.
- Frequent commits: one commit per task, message prefix `feat:`/`test:`/`docs:`.

## File Structure

```
extnded-thotz/
  assets/logo.png              # user-provided goat logo (already present)
  requirements.txt             # runtime deps
  requirements-dev.txt         # pytest, pywin32 (fixture generation)
  conftest.py                  # empty; puts project root on sys.path for pytest
  extnded_thotz/
    __init__.py                # version + app display name
    config.py                  # defaults, load/save %APPDATA%\ExtndedThotz\config.json
    cleanup.py                 # rule-based transcript cleanup + voice commands
    llm_cleanup.py             # optional OpenAI polish tier (failure = passthrough)
    audio_io.py                # WAV read/write, float32<->int16, linear resample
    recorder.py                # mic capture at device rate, resampled to 16 kHz
    transcriber.py             # LocalWhisperBackend / OpenAIBackend / make_backend + CLI
    injector.py                # clipboard paste w/ restore, char-typing fallback
    hotkey.py                  # HotkeyController state machine + KeyboardBinder
    history.py                 # append-only JSONL dictation history
    overlay.py                 # floating status pill (Tk, main thread)
    tray.py                    # pystray icon from logo.png, recording badge
    app.py                     # DictationApp orchestrator
    __main__.py                # entry point, logging, single-instance, --smoke/--once
    settings_ui.py             # separate-process tkinter settings window
  scripts/make_fixture.py      # SAPI TTS -> tests/fixtures/dictation.wav (dev only)
  tests/
    test_config.py  test_cleanup.py  test_audio_io.py  test_recorder.py
    test_transcriber_local.py  test_injector.py  test_hotkey.py
    test_history.py  test_llm_cleanup.py
  README.md
```

Threading model: main thread = Tk mainloop + overlay + UI queue pump (50 ms). `keyboard` hook thread fires controller callbacks. Each dictation spawns one worker thread (transcribe → clean → inject → history). Config-watcher daemon polls mtime every 2 s. pystray runs via `run_detached()`. State machine: IDLE → RECORDING → PROCESSING → IDLE; new recordings are ignored while PROCESSING (busy flag); ESC cancels a recording.

---

### Task 1: Scaffold + config module

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `conftest.py`, `extnded_thotz/__init__.py`, `extnded_thotz/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.DEFAULTS: dict`, `config.load_config(path=None) -> dict`, `config.save_config(cfg, path=None)`, `config.config_dir() -> Path`, `config.config_path() -> Path`, `config.resolve_api_key(cfg) -> str`, `APP_NAME = "ExtndedThotz"`.

- [ ] **Step 1: Write scaffold files**

`.gitignore`:
```
__pycache__/
*.py[cod]
.pytest_cache/
tests/fixtures/
dist/
build/
*.egg-info/
```

`requirements.txt`:
```
sounddevice>=0.5
numpy>=2.0
keyboard>=0.13.5
pystray>=0.19.5
Pillow>=10.0
pyperclip>=1.9
faster-whisper>=1.2
openai>=1.40
```

`requirements-dev.txt`:
```
pytest>=8
pywin32>=311
```

`conftest.py`: empty file (its presence puts the project root on `sys.path` for pytest).

`extnded_thotz/__init__.py`:
```python
"""Extnded Thotz — hold a key, speak, and polished text lands in the focused app."""

__version__ = "0.1.0"
APP_DISPLAY_NAME = "Extnded Thotz"
```

- [ ] **Step 2: Write the failing test** — `tests/test_config.py`:

```python
import json

from extnded_thotz import config


def test_defaults_offline_first():
    cfg = config.load_config(path="Z:/does/not/exist.json")
    assert cfg["backend"] == "auto"
    assert cfg["model_size"] == "base"
    assert cfg["hotkey"] == "right ctrl"
    assert cfg["mode"] == "hold"
    assert cfg["injection"] == "paste"


def test_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = config.load_config(path=p)
    cfg["hotkey"] = "f9"
    cfg["mode"] = "toggle"
    config.save_config(cfg, path=p)
    again = config.load_config(path=p)
    assert again["hotkey"] == "f9"
    assert again["mode"] == "toggle"


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    assert config.load_config(path=p) == dict(config.DEFAULTS)


def test_unknown_keys_dropped(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"hotkey": "f8", "evil": 1}), encoding="utf-8")
    cfg = config.load_config(path=p)
    assert cfg["hotkey"] == "f8"
    assert "evil" not in cfg


def test_resolve_api_key_env_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    assert config.resolve_api_key({"openai_api_key": ""}) == "sk-env"
    assert config.resolve_api_key({"openai_api_key": "sk-cfg"}) == "sk-cfg"
    monkeypatch.delenv("OPENAI_API_KEY")
    assert config.resolve_api_key({"openai_api_key": ""}) == ""
```

- [ ] **Step 3: Run to verify failure** — `python -m pytest tests/test_config.py -q` → import error (config missing).

- [ ] **Step 4: Implement** — `extnded_thotz/config.py`:

```python
"""Settings persistence: %APPDATA%\\ExtndedThotz\\config.json with safe defaults."""

import json
import os
from pathlib import Path

APP_NAME = "ExtndedThotz"

DEFAULTS = {
    "hotkey": "right ctrl",     # key held (or toggled) to dictate
    "mode": "hold",             # hold | toggle
    "backend": "auto",          # auto (openai if key, else local) | local | openai
    "model_size": "base",       # faster-whisper: tiny|base|small|medium|large-v3
    "language": None,           # None = auto-detect, else ISO code like "en"
    "llm_cleanup": "auto",      # auto (on when key present) | on | off
    "remove_fillers": True,
    "voice_commands": True,     # "new line" / "new paragraph"
    "injection": "paste",       # paste | type
    "restore_clipboard": True,
    "append_space": False,
    "show_overlay": True,
    "preload_model": True,
    "openai_api_key": "",
    "openai_stt_model": "whisper-1",
    "openai_llm_model": "gpt-4o-mini",
}


def config_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home())
    return Path(root) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config(path=None) -> dict:
    p = Path(path) if path else config_path()
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return cfg
    if isinstance(data, dict):
        for key, value in data.items():
            if key in DEFAULTS:
                cfg[key] = value
    return cfg


def save_config(cfg: dict, path=None) -> None:
    p = Path(path) if path else config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    known = {k: cfg[k] for k in DEFAULTS if k in cfg}
    p.write_text(json.dumps(known, indent=2), encoding="utf-8")


def resolve_api_key(cfg: dict) -> str:
    return (cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()
```

- [ ] **Step 5: Run to verify pass** — `python -m pytest tests/test_config.py -q` → 5 passed.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: project scaffold and config module"`

---

### Task 2: Transcript cleanup engine

**Files:**
- Create: `extnded_thotz/cleanup.py`
- Test: `tests/test_cleanup.py`

**Interfaces:**
- Produces: `clean_transcript(text, *, remove_fillers_enabled=True, voice_commands_enabled=True) -> str` (plus helpers `apply_voice_commands`, `remove_fillers`, `normalize_spacing`, `capitalize_sentences`).

- [ ] **Step 1: Write the failing test** — `tests/test_cleanup.py`:

```python
from extnded_thotz.cleanup import clean_transcript


def test_removes_leading_filler():
    assert clean_transcript("um hello world") == "Hello world"


def test_removes_mid_sentence_filler_with_comma():
    assert clean_transcript("I think, uh, we should ship it.") == "I think, we should ship it."


def test_fillers_can_be_disabled():
    assert clean_transcript("um hi", remove_fillers_enabled=False) == "Um hi"


def test_new_line_command():
    assert clean_transcript("first point new line second point") == "First point\nSecond point"


def test_new_paragraph_command():
    assert clean_transcript("one new paragraph two") == "One\n\nTwo"


def test_command_swallows_adjacent_punctuation():
    assert clean_transcript("note, new line, buy milk") == "Note\nBuy milk"


def test_voice_commands_can_be_disabled():
    out = clean_transcript("go to a new line please", voice_commands_enabled=False)
    assert out == "Go to a new line please"


def test_spacing_before_punctuation_fixed():
    assert clean_transcript("hello ,  world .") == "Hello, world."


def test_space_added_after_comma():
    assert clean_transcript("hello,world") == "Hello, world"


def test_capitalizes_each_sentence():
    assert clean_transcript("this is one. this is two.") == "This is one. This is two."


def test_empty_and_whitespace():
    assert clean_transcript("") == ""
    assert clean_transcript("   ") == ""


def test_filler_like_words_kept():
    # 'um' inside words must never be touched
    assert clean_transcript("the summer hummus is yummy") == "The summer hummus is yummy"
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_cleanup.py -q` → import error.

- [ ] **Step 3: Implement** — `extnded_thotz/cleanup.py`:

```python
"""Rule-based cleanup of raw transcripts: fillers, voice commands, spacing, caps.

Deterministic tier that always runs; the optional LLM polish tier
(llm_cleanup.py) runs after this when enabled.
"""

import re

_FILLER_RE = re.compile(r"(^|\s)(?:um+|uh+|uhm+|erm+|hmm+|mmm+)[,.]?(?=\s|$)", re.IGNORECASE)

_COMMANDS = [
    (re.compile(r"[,.;\s]*\bnew\s+paragraph\b[,.;\s]*", re.IGNORECASE), "\n\n"),
    (re.compile(r"[,.;\s]*\bnew\s+line\b[,.;\s]*", re.IGNORECASE), "\n"),
]


def apply_voice_commands(text: str) -> str:
    for pattern, replacement in _COMMANDS:
        text = pattern.sub(replacement, text)
    return text


def remove_fillers(text: str) -> str:
    return _FILLER_RE.sub(r"\1", text)


def normalize_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,;:])(?=[A-Za-z])", r"\1 ", text)
    text = re.sub(r"([.!?])(?=[A-Z])", r"\1 ", text)
    return text


def capitalize_sentences(text: str) -> str:
    return re.sub(
        r"(^|[.!?][\"')\]]?\s+|\n\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )


def clean_transcript(text, *, remove_fillers_enabled=True, voice_commands_enabled=True) -> str:
    if not text:
        return ""
    out = text.strip()
    if voice_commands_enabled:
        out = apply_voice_commands(out)
    if remove_fillers_enabled:
        out = remove_fillers(out)
    out = normalize_spacing(out).strip()  # strip before caps: removed leading fillers leave a space that would block the ^ anchor
    out = capitalize_sentences(out)
    return out.strip()
```

Known tradeoff (documented, config-escapable): literal phrases "new line"/"new paragraph" are always treated as commands when `voice_commands` is on — same behavior as commercial dictation tools.

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_cleanup.py -q` → 13 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat: rule-based transcript cleanup engine"`

---

### Task 3: Audio I/O helpers

**Files:**
- Create: `extnded_thotz/audio_io.py`
- Test: `tests/test_audio_io.py`

**Interfaces:**
- Produces: `TARGET_RATE = 16000`, `float32_to_wav_bytes(audio, sample_rate=TARGET_RATE) -> bytes`, `save_wav(path, audio, sample_rate=TARGET_RATE)`, `load_wav_float32(path) -> (np.ndarray float32 mono, int rate)`, `resample_linear(audio, src_rate, dst_rate=TARGET_RATE) -> np.ndarray`.

- [ ] **Step 1: Write the failing test** — `tests/test_audio_io.py`:

```python
import io
import wave

import numpy as np

from extnded_thotz.audio_io import (
    TARGET_RATE,
    float32_to_wav_bytes,
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
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_audio_io.py -q` → import error.

- [ ] **Step 3: Implement** — `extnded_thotz/audio_io.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_audio_io.py -q` → 5 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat: WAV read/write and resampling helpers"`

---

### Task 4: Microphone recorder

**Files:**
- Create: `extnded_thotz/recorder.py`
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: `audio_io.resample_linear`, `audio_io.TARGET_RATE`.
- Produces: `Recorder()` with `.start()`, `.stop() -> np.ndarray (16 kHz mono float32)`, `.cancel()`, `.is_recording: bool`, `Recorder.input_device_available() -> bool`, `MicUnavailableError`.

- [ ] **Step 1: Write the failing test** — `tests/test_recorder.py`:

```python
import time

import numpy as np
import pytest

from extnded_thotz.recorder import MicUnavailableError, Recorder


def test_short_capture_or_graceful_error():
    rec = Recorder()
    if not Recorder.input_device_available():
        with pytest.raises(MicUnavailableError):
            rec.start()
        return
    rec.start()
    assert rec.is_recording
    time.sleep(0.3)
    audio = rec.stop()
    assert not rec.is_recording
    assert audio.dtype == np.float32
    assert audio.ndim == 1


def test_cancel_discards():
    rec = Recorder()
    if not Recorder.input_device_available():
        pytest.skip("no input device")
    rec.start()
    time.sleep(0.1)
    rec.cancel()
    assert not rec.is_recording
    # stopping again returns empty rather than raising
    assert rec.stop().size == 0
```

- [ ] **Step 2: Run to verify failure**, then **Step 3: Implement** — `extnded_thotz/recorder.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_recorder.py -q` (uses the real default mic when present; skips/asserts graceful error otherwise).

- [ ] **Step 5: Commit** — `git commit -m "feat: microphone recorder with device-rate capture"`

---

### Task 5: Transcription backends + TTS fixture E2E test

**Files:**
- Create: `extnded_thotz/transcriber.py`, `scripts/make_fixture.py`
- Test: `tests/test_transcriber_local.py`

**Interfaces:**
- Consumes: `audio_io` helpers.
- Produces: `LocalWhisperBackend(model_size)` / `OpenAIBackend(api_key, model)` each with `.name: str`, `.load() -> self`, `.transcribe(audio_f32, language=None) -> str`; `make_backend(cfg, api_key="") -> backend`; `TranscriptionError`; CLI `python -m extnded_thotz.transcriber file.wav [model_size]`.

- [ ] **Step 1: Write the fixture generator** — `scripts/make_fixture.py`:

```python
"""Generate a spoken-sentence WAV fixture with Windows SAPI TTS (dev-only).

Lets the STT end-to-end test run without a human speaking into a mic:
    python scripts/make_fixture.py
"""

from pathlib import Path

SENTENCE = "Hello world. This is a test of extended thoughts dictation."
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "dictation.wav"

SAFT_16K_16BIT_MONO = 22
SSF_CREATE_FOR_WRITE = 3


def main() -> None:
    import win32com.client

    OUT.parent.mkdir(parents=True, exist_ok=True)
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    try:
        fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
        fmt.Type = SAFT_16K_16BIT_MONO
        stream.Format = fmt
    except Exception:
        pass  # default format is fine; loader resamples
    stream.Open(str(OUT), SSF_CREATE_FOR_WRITE)
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.AudioOutputStream = stream
    voice.Speak(SENTENCE)
    stream.Close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing E2E test** — `tests/test_transcriber_local.py`:

```python
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
```

- [ ] **Step 3: Implement** — `extnded_thotz/transcriber.py`:

```python
"""Speech-to-text backends: local faster-whisper (offline) and OpenAI (cloud)."""

import io
import sys
import threading

from .audio_io import TARGET_RATE, float32_to_wav_bytes, load_wav_float32, resample_linear


class TranscriptionError(RuntimeError):
    """Transcription failed (model load, decode, or network error)."""


class LocalWhisperBackend:
    name = "local"

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise TranscriptionError("faster-whisper is not installed") from exc
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self

    def transcribe(self, audio, language=None) -> str:
        if audio.size < TARGET_RATE // 10:  # under 0.1 s of audio
            return ""
        self.load()
        try:
            segments, _info = self._model.transcribe(
                audio, language=language, beam_size=5, vad_filter=True
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc


class OpenAIBackend:
    name = "openai"

    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def load(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        return self

    def transcribe(self, audio, language=None) -> str:
        self.load()
        buf = io.BytesIO(float32_to_wav_bytes(audio))
        buf.name = "dictation.wav"
        kwargs = {"model": self.model, "file": buf}
        if language:
            kwargs["language"] = language
        try:
            return self._client.audio.transcriptions.create(**kwargs).text.strip()
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc


def make_backend(cfg: dict, api_key: str = ""):
    choice = cfg.get("backend", "auto")
    if choice == "openai" or (choice == "auto" and api_key):
        return OpenAIBackend(api_key, cfg.get("openai_stt_model", "whisper-1"))
    return LocalWhisperBackend(cfg.get("model_size", "base"))


def _main(argv):
    if not argv:
        print("usage: python -m extnded_thotz.transcriber file.wav [model_size]")
        return 2
    audio, rate = load_wav_float32(argv[0])
    audio = resample_linear(audio, rate, TARGET_RATE)
    size = argv[1] if len(argv) > 1 else "base"
    print(LocalWhisperBackend(size).transcribe(audio))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 4: Generate fixture and run** — `python scripts/make_fixture.py` then `python -m pytest tests/test_transcriber_local.py -q`. First run downloads the `tiny` model (~75 MB) from Hugging Face. Expected: 3 passed. If `vad_filter=True` eats the robotic TTS voice, set `vad_filter=False` and re-run.

- [ ] **Step 5: Commit** — `git commit -m "feat: local whisper + openai transcription backends with TTS-fixture e2e test"`

---

### Task 6: Text injector

**Files:**
- Create: `extnded_thotz/injector.py`
- Test: `tests/test_injector.py`

**Interfaces:**
- Produces: `inject_text(text, method="paste", restore_clipboard=True, keyboard_module=None, pre_delay=0.15, restore_delay=0.6)`, `_set_clipboard(text)` (used by tray "copy last transcript").

- [ ] **Step 1: Write the failing test** — `tests/test_injector.py`:

```python
import time

from extnded_thotz import injector


class FakeKeyboard:
    def __init__(self):
        self.sent = []
        self.wrote = []

    def send(self, combo):
        self.sent.append(combo)

    def write(self, text, delay=0):
        self.wrote.append(text)


def _patch_clipboard(monkeypatch):
    clip = {"value": "OLD"}
    monkeypatch.setattr(injector, "_get_clipboard", lambda: clip["value"])
    monkeypatch.setattr(injector, "_set_clipboard", lambda t: clip.__setitem__("value", t))
    return clip


def test_paste_sets_clipboard_sends_ctrl_v_and_restores(monkeypatch):
    clip = _patch_clipboard(monkeypatch)
    kb = FakeKeyboard()
    injector.inject_text("hi there", keyboard_module=kb, pre_delay=0, restore_delay=0.05)
    assert kb.sent == ["ctrl+v"]
    time.sleep(0.3)
    assert clip["value"] == "OLD"


def test_paste_without_restore_leaves_text(monkeypatch):
    clip = _patch_clipboard(monkeypatch)
    kb = FakeKeyboard()
    injector.inject_text("keep me", keyboard_module=kb, restore_clipboard=False, pre_delay=0)
    time.sleep(0.2)
    assert clip["value"] == "keep me"


def test_type_mode_uses_write(monkeypatch):
    _patch_clipboard(monkeypatch)
    kb = FakeKeyboard()
    injector.inject_text("typed", method="type", keyboard_module=kb, pre_delay=0)
    assert kb.wrote == ["typed"]
    assert kb.sent == []


def test_empty_text_is_noop(monkeypatch):
    clip = _patch_clipboard(monkeypatch)
    kb = FakeKeyboard()
    injector.inject_text("", keyboard_module=kb, pre_delay=0)
    assert kb.sent == [] and kb.wrote == [] and clip["value"] == "OLD"
```

- [ ] **Step 2: Run to verify failure**, then **Step 3: Implement** — `extnded_thotz/injector.py`:

```python
"""Insert text into the focused window.

Default method swaps the clipboard, sends Ctrl+V, then restores the previous
clipboard shortly after — the same approach commercial dictation tools use
because per-character typing is slow and breaks in some apps. A `type`
fallback (SendInput unicode typing via keyboard.write) exists for apps that
block paste.
"""

import threading
import time


def _default_keyboard():
    import keyboard

    return keyboard


def _get_clipboard() -> str:
    import pyperclip

    return pyperclip.paste()


def _set_clipboard(text: str) -> None:
    import pyperclip

    pyperclip.copy(text)


def inject_text(
    text: str,
    method: str = "paste",
    restore_clipboard: bool = True,
    keyboard_module=None,
    pre_delay: float = 0.15,
    restore_delay: float = 0.6,
) -> None:
    if not text:
        return
    kb = keyboard_module or _default_keyboard()
    if pre_delay:
        time.sleep(pre_delay)  # let the hotkey's physical modifiers settle
    if method == "type":
        kb.write(text, delay=0.005)
        return
    previous = None
    if restore_clipboard:
        try:
            previous = _get_clipboard()
        except Exception:
            previous = None
    _set_clipboard(text)
    time.sleep(0.05)
    kb.send("ctrl+v")
    if restore_clipboard and previous is not None:
        def _restore(value=previous):
            try:
                _set_clipboard(value)
            except Exception:
                pass

        timer = threading.Timer(restore_delay, _restore)
        timer.daemon = True
        timer.start()
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_injector.py -q` → 4 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat: clipboard-paste text injector with restore and typing fallback"`

---

### Task 7: Hotkey state machine + keyboard binding

**Files:**
- Create: `extnded_thotz/hotkey.py`
- Test: `tests/test_hotkey.py`

**Interfaces:**
- Produces: `HotkeyController(on_start, on_stop, on_cancel=None, mode="hold", min_hold_s=0.25, clock=time.monotonic)` with `.press()`, `.release()`, `.cancel()`, `.mode` attribute (mutable); `KeyboardBinder(controller, key)` with `.bind()`, `.unbind()`, `.rebind(new_key)`.
- Consumed by: `app.py` (controller callbacks run on the `keyboard` hook thread).

- [ ] **Step 1: Write the failing test** — `tests/test_hotkey.py`:

```python
from extnded_thotz.hotkey import HotkeyController


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _make(mode="hold"):
    calls = []
    clock = FakeClock()
    ctl = HotkeyController(
        on_start=lambda: calls.append("start"),
        on_stop=lambda: calls.append("stop"),
        on_cancel=lambda: calls.append("cancel"),
        mode=mode,
        min_hold_s=0.25,
        clock=clock,
    )
    return ctl, calls, clock


def test_hold_press_release_cycle():
    ctl, calls, clock = _make()
    ctl.press()
    clock.now = 1.0
    ctl.release()
    assert calls == ["start", "stop"]


def test_hold_autorepeat_ignored():
    ctl, calls, clock = _make()
    ctl.press()
    ctl.press()
    ctl.press()
    clock.now = 1.0
    ctl.release()
    assert calls == ["start", "stop"]


def test_hold_quick_tap_cancels():
    ctl, calls, clock = _make()
    ctl.press()
    clock.now = 0.1  # under min_hold_s
    ctl.release()
    assert calls == ["start", "cancel"]


def test_toggle_mode():
    ctl, calls, clock = _make(mode="toggle")
    ctl.press()
    ctl.release()
    assert calls == ["start"]
    clock.now = 2.0
    ctl.press()
    ctl.release()
    assert calls == ["start", "stop"]


def test_explicit_cancel_only_while_recording():
    ctl, calls, clock = _make()
    ctl.cancel()
    assert calls == []
    ctl.press()
    ctl.cancel()
    assert calls == ["start", "cancel"]
    clock.now = 1.0
    ctl.release()
    assert calls == ["start", "cancel"]  # release after cancel is a no-op
```

- [ ] **Step 2: Run to verify failure**, then **Step 3: Implement** — `extnded_thotz/hotkey.py`:

```python
"""Push-to-talk / toggle hotkey handling.

HotkeyController is a pure state machine (unit-testable, no OS hooks).
KeyboardBinder wires it to the `keyboard` library's global hooks and also
listens for ESC to cancel an in-flight recording.
"""

import time


class HotkeyController:
    def __init__(self, on_start, on_stop, on_cancel=None, mode="hold",
                 min_hold_s=0.25, clock=time.monotonic):
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel or on_stop
        self.mode = mode
        self.min_hold_s = min_hold_s
        self.clock = clock
        self._recording = False
        self._pressed = False
        self._started_at = 0.0

    @property
    def is_recording(self) -> bool:
        return self._recording

    def press(self) -> None:
        if self._pressed:
            return  # OS key auto-repeat
        self._pressed = True
        if self.mode == "toggle":
            if self._recording:
                self._recording = False
                self.on_stop()
            else:
                self._recording = True
                self._started_at = self.clock()
                self.on_start()
            return
        if not self._recording:
            self._recording = True
            self._started_at = self.clock()
            self.on_start()

    def release(self) -> None:
        self._pressed = False
        if self.mode != "hold" or not self._recording:
            return
        self._recording = False
        if self.clock() - self._started_at < self.min_hold_s:
            self.on_cancel()
        else:
            self.on_stop()

    def cancel(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self.on_cancel()


class KeyboardBinder:
    def __init__(self, controller: HotkeyController, key: str = "right ctrl"):
        self.controller = controller
        self.key = key
        self._handles = []

    def bind(self) -> None:
        import keyboard

        self._handles = [
            keyboard.on_press_key(self.key, lambda e: self.controller.press(), suppress=False),
            keyboard.on_release_key(self.key, lambda e: self.controller.release(), suppress=False),
            keyboard.on_press_key("esc", lambda e: self.controller.cancel(), suppress=False),
        ]

    def unbind(self) -> None:
        import keyboard

        for handle in self._handles:
            try:
                keyboard.unhook(handle)
            except (KeyError, ValueError):
                pass
        self._handles = []

    def rebind(self, new_key: str) -> None:
        self.unbind()
        self.key = new_key
        self.bind()
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_hotkey.py -q` → 5 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat: push-to-talk hotkey state machine and keyboard binder"`

---

### Task 8: History log

**Files:**
- Create: `extnded_thotz/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Produces: `History(path)` with `.append(text, duration_s=0.0, backend="")` and `.last(n=20) -> list[dict]`.

- [ ] **Step 1: Write the failing test** — `tests/test_history.py`:

```python
from extnded_thotz.history import History


def test_append_and_read_back(tmp_path):
    h = History(tmp_path / "h.jsonl")
    h.append("first", 1.2, "local")
    h.append("second", 0.8, "local")
    entries = h.last()
    assert [e["text"] for e in entries] == ["first", "second"]
    assert entries[0]["backend"] == "local"
    assert "ts" in entries[0]


def test_last_n_limits(tmp_path):
    h = History(tmp_path / "h.jsonl")
    for i in range(30):
        h.append(f"t{i}")
    assert len(h.last(5)) == 5
    assert h.last(5)[-1]["text"] == "t29"


def test_corrupt_lines_skipped(tmp_path):
    p = tmp_path / "h.jsonl"
    h = History(p)
    h.append("good")
    with open(p, "a", encoding="utf-8") as f:
        f.write("{broken\n")
    h.append("also good")
    assert [e["text"] for e in h.last()] == ["good", "also good"]


def test_empty_history(tmp_path):
    assert History(tmp_path / "none.jsonl").last() == []
```

- [ ] **Step 2: Run to verify failure**, then **Step 3: Implement** — `extnded_thotz/history.py`:

```python
"""Append-only JSONL history of dictations."""

import json
from datetime import datetime
from pathlib import Path


class History:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, text: str, duration_s: float = 0.0, backend: str = "") -> None:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "text": text,
            "duration_s": round(float(duration_s), 2),
            "backend": backend,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def last(self, n: int = 20) -> list:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries[-n:]
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_history.py -q` → 4 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat: jsonl dictation history"`

---

### Task 9: Optional LLM polish tier

**Files:**
- Create: `extnded_thotz/llm_cleanup.py`
- Test: `tests/test_llm_cleanup.py`

**Interfaces:**
- Produces: `polish(text, api_key, model="gpt-4o-mini", timeout_s=10.0, _client=None) -> str` (returns input unchanged on any failure), `should_polish(cfg, api_key) -> bool`, `SYSTEM_PROMPT`.

- [ ] **Step 1: Write the failing test** — `tests/test_llm_cleanup.py`:

```python
from extnded_thotz.llm_cleanup import polish, should_polish


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        outer = self

        class _Completions:
            def create(self, **kwargs):
                if outer.error:
                    raise outer.error
                return type("R", (), {"choices": [_Msg(outer.reply)]})()

        self.chat = type("C", (), {"completions": _Completions()})()


def test_polish_returns_cleaned_text():
    out = polish("um hello", "sk-x", _client=FakeClient(reply="Hello."))
    assert out == "Hello."


def test_polish_falls_back_on_error():
    out = polish("original text", "sk-x", _client=FakeClient(error=RuntimeError("boom")))
    assert out == "original text"


def test_polish_falls_back_on_empty_reply():
    assert polish("keep", "sk-x", _client=FakeClient(reply="")) == "keep"


def test_polish_noop_without_key_or_text():
    assert polish("text", "") == "text"
    assert polish("", "sk-x") == ""


def test_should_polish_matrix():
    assert should_polish({"llm_cleanup": "on"}, "") is True
    assert should_polish({"llm_cleanup": "auto"}, "sk-x") is True
    assert should_polish({"llm_cleanup": "auto"}, "") is False
    assert should_polish({"llm_cleanup": "off"}, "sk-x") is False
```

- [ ] **Step 2: Run to verify failure**, then **Step 3: Implement** — `extnded_thotz/llm_cleanup.py`:

```python
"""Optional LLM polish pass for dictated text (OpenAI). Fails soft: any error
returns the rule-cleaned text unchanged, so dictation never breaks offline."""

SYSTEM_PROMPT = (
    "You clean up dictated speech-to-text output. Fix punctuation, capitalization, "
    "and obvious transcription artifacts; remove filler words and false starts; keep "
    "the speaker's own words and meaning; never add content and never answer questions "
    "that appear in the text. Preserve line breaks. Return ONLY the cleaned text."
)


def should_polish(cfg: dict, api_key: str) -> bool:
    mode = cfg.get("llm_cleanup", "auto")
    if mode == "on":
        return True
    if mode == "auto":
        return bool(api_key)
    return False


def polish(text: str, api_key: str, model: str = "gpt-4o-mini",
           timeout_s: float = 10.0, _client=None) -> str:
    if not text.strip() or (not api_key and _client is None):
        return text
    try:
        client = _client
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=timeout_s)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        cleaned = (response.choices[0].message.content or "").strip()
        return cleaned or text
    except Exception:
        return text
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_llm_cleanup.py -q` → 5 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat: optional fail-soft LLM polish tier"`

---

### Task 10: Overlay pill, tray icon, orchestrator, entry point

**Files:**
- Create: `extnded_thotz/overlay.py`, `extnded_thotz/tray.py`, `extnded_thotz/app.py`, `extnded_thotz/__main__.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `Overlay(root)` with `.show(text, fg=...)`, `.hide()`, `.flash(text, fg=..., ms=1200)`; `tray.load_logo_image(size=64, recording=False) -> PIL.Image`; `tray.build_tray(app) -> pystray.Icon`; `DictationApp(root, overlay, cfg)` with `.start()`, `.quit()`, `.tray_icon`, `.enabled`, `.copy_last()`, `.open_settings()`; CLI `python -m extnded_thotz [--smoke SECONDS] [--once WAV]`.

- [ ] **Step 1: Implement `overlay.py`** (Tk main thread only):

```python
"""Floating status pill shown while recording/processing. Main thread only."""

import tkinter as tk


class Overlay:
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        self.win.configure(bg="#0b0b0b")
        self.label = tk.Label(
            self.win, text="", fg="#ffffff", bg="#0b0b0b",
            font=("Segoe UI", 11, "bold"), padx=16, pady=7,
        )
        self.label.pack(fill="both", expand=True)
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        self.win.geometry(f"+{(screen_w - 200) // 2}+{screen_h - 130}")
        self._flash_job = None
        self.win.withdraw()

    def show(self, text: str, fg: str = "#ff5c5c") -> None:
        self._cancel_flash()
        self.label.config(text=text, fg=fg)
        self.win.deiconify()
        self.win.lift()

    def hide(self) -> None:
        self._cancel_flash()
        self.win.withdraw()

    def flash(self, text: str, fg: str = "#ffb3b3", ms: int = 1200) -> None:
        self.show(text, fg)
        self._flash_job = self.root.after(ms, self.hide)

    def _cancel_flash(self) -> None:
        if self._flash_job is not None:
            try:
                self.root.after_cancel(self._flash_job)
            except Exception:
                pass
            self._flash_job = None
```

- [ ] **Step 2: Implement `tray.py`** (goat logo, red recording badge):

```python
"""System tray icon built from the Extnded Thotz goat logo."""

from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


def load_logo_image(size: int = 64, recording: bool = False):
    from PIL import Image, ImageDraw

    logo = ASSET_DIR / "logo.png"
    if logo.exists():
        img = Image.open(logo).convert("RGBA").resize((size, size), Image.LANCZOS)
    else:  # fallback glyph if the asset is missing
        img = Image.new("RGBA", (size, size), (11, 11, 11, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([size * 0.3, size * 0.15, size * 0.7, size * 0.6], fill="white")
        draw.rectangle([size * 0.45, size * 0.6, size * 0.55, size * 0.85], fill="white")
    if recording:
        draw = ImageDraw.Draw(img)
        r = size // 5
        draw.ellipse([size - 2 * r - 2, size - 2 * r - 2, size - 2, size - 2],
                     fill=(230, 60, 60, 255))
    return img


def build_tray(app):
    import pystray
    from pystray import Menu, MenuItem as Item

    menu = Menu(
        Item("Extnded Thotz", None, enabled=False),
        Item("Enabled", lambda icon, item: _toggle_enabled(app),
             checked=lambda item: app.enabled),
        Item("Copy last transcript", lambda icon, item: app.copy_last()),
        Item("Settings…", lambda icon, item: app.open_settings()),
        Item("Quit", lambda icon, item: app.quit()),
    )
    return pystray.Icon("extnded_thotz", load_logo_image(),
                        "Extnded Thotz — dictation", menu)


def _toggle_enabled(app):
    app.enabled = not app.enabled
```

- [ ] **Step 3: Implement `app.py`** (orchestrator; UI marshaled through a queue pumped on the Tk main thread):

```python
"""DictationApp: hotkey → recorder → transcriber → cleanup → injector."""

import logging
import queue
import subprocess
import sys
import threading
import time

from . import config as config_mod
from . import llm_cleanup
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
            self.ui(lambda: self.overlay.show("● Listening"))

    def _hotkey_stop(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        duration = time.monotonic() - self._started_at
        self._set_tray_recording(False)
        if audio.size < MIN_AUDIO_SECONDS * 16000:
            self.ui(lambda: self.overlay.flash("· too short"))
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
        log.info("Config reloaded (hotkey=%s, mode=%s, backend=%s)",
                 new["hotkey"], new["mode"], self.backend.name)
```

- [ ] **Step 4: Implement `__main__.py`**:

```python
"""Entry point: python -m extnded_thotz [--smoke SECONDS] [--once WAV]"""

import argparse
import logging
import logging.handlers
import socket
import sys

from . import APP_DISPLAY_NAME, config as config_mod

SINGLETON_PORT = 48653


def _setup_logging():
    log_dir = config_mod.config_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def _single_instance_guard():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", SINGLETON_PORT))
        return sock
    except OSError:
        sock.close()
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="extnded-thotz", description=APP_DISPLAY_NAME)
    parser.add_argument("--smoke", type=float, default=0,
                        help="run for N seconds then exit cleanly (self-test)")
    parser.add_argument("--once", metavar="WAV",
                        help="transcribe a WAV file and print the text (no GUI)")
    args = parser.parse_args(argv)
    _setup_logging()
    log = logging.getLogger("extnded_thotz")

    if args.once:
        from .transcriber import _main as transcribe_main

        return transcribe_main([args.once])

    guard = _single_instance_guard()
    if guard is None:
        print(f"{APP_DISPLAY_NAME} is already running.")
        return 1

    import tkinter as tk

    from .app import DictationApp
    from .overlay import Overlay
    from .tray import build_tray

    cfg = config_mod.load_config()
    config_mod.save_config(cfg)  # materialize defaults on first run

    root = tk.Tk()
    root.withdraw()
    root.title(APP_DISPLAY_NAME)
    overlay = Overlay(root)
    app = DictationApp(root, overlay, cfg)
    try:
        icon = build_tray(app)
        app.tray_icon = icon
        icon.run_detached()
    except Exception as exc:
        log.warning("Tray unavailable, continuing without it: %s", exc)
    app.start()
    log.info("ready")
    if args.smoke:
        root.after(int(args.smoke * 1000), app.quit)
    root.mainloop()
    guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Smoke test** — `python -m extnded_thotz --smoke 4`. Expected: stderr shows `Extnded Thotz ready — hold 'right ctrl' to dictate (backend=local, model=base)` then `ready`; process exits 0 within ~5 s; tray icon appears and disappears; no orphan process.

- [ ] **Step 6: Full test suite** — `python -m pytest -q` → all green.

- [ ] **Step 7: Commit** — `git commit -m "feat: overlay pill, goat tray icon, orchestrator, entry point"`

---

### Task 11: Settings window (separate process)

**Files:**
- Create: `extnded_thotz/settings_ui.py`

**Interfaces:**
- Consumes: `config.load_config/save_config/DEFAULTS`.
- Produces: `python -m extnded_thotz.settings_ui` opens a dark-themed form; Save writes config.json (the running app hot-reloads within ~2 s via its config watcher).

- [ ] **Step 1: Implement** — `extnded_thotz/settings_ui.py`:

```python
"""Settings window. Runs as its own process so the tray app's Tk loop and
this window never share a thread: python -m extnded_thotz.settings_ui"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import APP_DISPLAY_NAME, config as config_mod

BG = "#111111"
FG = "#f2f2f2"

HOTKEY_CHOICES = ["right ctrl", "right shift", "f8", "f9", "scroll lock", "pause"]
MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]


def main() -> None:
    cfg = config_mod.load_config()
    root = tk.Tk()
    root.title(f"{APP_DISPLAY_NAME} — Settings")
    root.configure(bg=BG)
    root.resizable(False, False)

    hotkey_var = tk.StringVar(value=cfg["hotkey"])
    mode_var = tk.StringVar(value=cfg["mode"])
    backend_var = tk.StringVar(value=cfg["backend"])
    model_var = tk.StringVar(value=cfg["model_size"])
    language_var = tk.StringVar(value=cfg["language"] or "")
    llm_var = tk.StringVar(value=cfg["llm_cleanup"])
    injection_var = tk.StringVar(value=cfg["injection"])
    api_key_var = tk.StringVar(value=cfg["openai_api_key"])
    fillers_var = tk.BooleanVar(value=cfg["remove_fillers"])
    commands_var = tk.BooleanVar(value=cfg["voice_commands"])
    restore_var = tk.BooleanVar(value=cfg["restore_clipboard"])
    overlay_var = tk.BooleanVar(value=cfg["show_overlay"])
    space_var = tk.BooleanVar(value=cfg["append_space"])

    body = tk.Frame(root, bg=BG, padx=16, pady=12)
    body.pack(fill="both", expand=True)
    row = 0

    def label(text):
        nonlocal row
        tk.Label(body, text=text, bg=BG, fg=FG, anchor="w").grid(
            row=row, column=0, sticky="w", pady=3, padx=(0, 10)
        )

    def combo(var, values):
        nonlocal row
        box = ttk.Combobox(body, textvariable=var, values=values, state="readonly", width=22)
        box.grid(row=row, column=1, sticky="we", pady=3)
        row += 1

    def check(text, var):
        nonlocal row
        tk.Checkbutton(
            body, text=text, variable=var, bg=BG, fg=FG,
            activebackground=BG, activeforeground=FG, selectcolor="#222222", anchor="w",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=1)
        row += 1

    label("Dictation key"); combo(hotkey_var, HOTKEY_CHOICES)
    label("Key mode"); combo(mode_var, ["hold", "toggle"])
    label("Transcription backend"); combo(backend_var, ["auto", "local", "openai"])
    label("Local model size"); combo(model_var, MODEL_CHOICES)
    label("Language (blank = auto)")
    entry = tk.Entry(body, textvariable=language_var, width=24, bg="#222222", fg=FG,
                     insertbackground=FG)
    entry.grid(row=row, column=1, sticky="we", pady=3); row += 1
    label("AI polish (needs API key)"); combo(llm_var, ["auto", "on", "off"])
    label("Insert method"); combo(injection_var, ["paste", "type"])
    label("OpenAI API key (optional)")
    key_entry = tk.Entry(body, textvariable=api_key_var, width=24, show="•",
                         bg="#222222", fg=FG, insertbackground=FG)
    key_entry.grid(row=row, column=1, sticky="we", pady=3); row += 1

    check("Remove filler words (um, uh…)", fillers_var)
    check('Voice commands ("new line", "new paragraph")', commands_var)
    check("Restore clipboard after paste", restore_var)
    check("Show status pill while dictating", overlay_var)
    check("Append trailing space after insert", space_var)

    def save() -> None:
        cfg.update(
            hotkey=hotkey_var.get(), mode=mode_var.get(), backend=backend_var.get(),
            model_size=model_var.get(), language=(language_var.get().strip() or None),
            llm_cleanup=llm_var.get(), injection=injection_var.get(),
            openai_api_key=api_key_var.get().strip(),
            remove_fillers=fillers_var.get(), voice_commands=commands_var.get(),
            restore_clipboard=restore_var.get(), show_overlay=overlay_var.get(),
            append_space=space_var.get(),
        )
        config_mod.save_config(cfg)
        messagebox.showinfo(APP_DISPLAY_NAME, "Saved. The running app picks this up within ~2 seconds.")
        root.destroy()

    buttons = tk.Frame(body, bg=BG)
    buttons.grid(row=row, column=0, columnspan=2, pady=(12, 0), sticky="e")
    tk.Button(buttons, text="Cancel", command=root.destroy, bg="#222222", fg=FG,
              activebackground="#333333", activeforeground=FG, width=10).pack(side="left", padx=6)
    tk.Button(buttons, text="Save", command=save, bg="#2e7d32", fg="white",
              activebackground="#388e3c", activeforeground="white", width=10).pack(side="left")

    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import + window opens** — `python -c "import extnded_thotz.settings_ui"` exits 0. (Visual check is part of the manual checklist.)

- [ ] **Step 3: Commit** — `git commit -m "feat: settings window (separate process, hot-reloaded config)"`

---

### Task 12: README, full-suite run, final verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md** covering: what it is (with logo at top), install (`pip install -r requirements.txt`), run (`python -m extnded_thotz`), usage (hold right Ctrl → speak → release; ESC cancels; voice commands), settings, config file location, history/log locations, offline vs cloud behavior, autostart via `shell:startup` shortcut, packaging note (PyInstaller command), manual test checklist, privacy statement (audio never leaves the machine unless an OpenAI backend/polish is enabled), independent-implementation note.

- [ ] **Step 2: Full suite** — `python -m pytest -q` → everything green.

- [ ] **Step 3: Re-run smoke** — `python -m extnded_thotz --smoke 4` → exit 0, "ready" logged.

- [ ] **Step 4: Commit** — `git commit -m "docs: README with usage, packaging, and manual test checklist"`

**Manual test checklist (requires a human voice + mic; goes in README):**
1. Run `python -m extnded_thotz`; goat icon appears in tray.
2. Focus Notepad, hold right Ctrl, say "hello world this is a test", release → text appears in Notepad; pill shows Listening → Transcribing → hides.
3. Say "first item new line second item" → two lines.
4. Hold key, press ESC → "Cancelled" pill, nothing inserted.
5. Tap key for <0.25 s → nothing happens (accidental-tap guard).
6. Copy something, dictate, paste → your original clipboard content is back.
7. Tray → Settings: change key to F9 + toggle mode, Save → within 2 s, F9 tap starts/stops dictation.
8. Tray → Quit → icon disappears, process exits, hotkey no longer reacts.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `keyboard` lib misses events in elevated (admin) windows | Documented limitation; run the app elevated if dictating into admin apps |
| Whisper `base` accuracy too low for fast speech | `model_size` config up to `large-v3`; `small` is a good CPU sweet spot |
| VAD filter trims very short utterances | 0.3 s minimum-audio guard; drop `vad_filter` if it misbehaves in practice |
| Paste blocked in some apps (elevated consoles) | `injection: "type"` fallback via SendInput unicode typing |
| Clipboard restore races with slow apps | 0.6 s restore delay, config-off switch |
| Tk overlay glitches on multi-monitor setups | Overlay is `show_overlay: false`-able; tray icon still signals recording |
| First model download needs network | One-time; documented in README |

## Post-MVP roadmap (not in this plan)

Streaming partial transcripts, hands-free VAD mode, personal dictionary (via Whisper `initial_prompt` biasing), per-app tone profiles (foreground process detection), command mode ("delete that", "send it"), PyInstaller one-file build + installer + code signing, auto-update, macOS port.

## Self-Review

- **Spec coverage:** hotkey→record→transcribe→cleanup→inject loop (Tasks 4–7, 10), offline-first (Task 5 local backend, no key needed), Wispr-style pill + tray + settings + history (Tasks 8, 10, 11), AI polish tier (Task 9), user branding (Task 10 tray uses `assets/logo.png`, display name everywhere). ✓
- **Placeholder scan:** all steps carry complete code; no TBDs. ✓
- **Type consistency:** `clean_transcript` kwargs match app.py call sites; backend `.name/.load/.transcribe` uniform across both backends; `Overlay.show/hide/flash` signatures match app.py usage; `HotkeyController.press/release/cancel` match KeyboardBinder bindings. ✓
