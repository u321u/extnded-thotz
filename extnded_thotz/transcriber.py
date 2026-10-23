"""Speech-to-text backends: local faster-whisper (offline) and OpenAI (cloud)."""

import io
import logging
import shutil
import sys
import threading
from pathlib import Path

from .audio_io import (
    TARGET_RATE,
    float32_to_wav_bytes,
    is_unusable,
    load_wav_float32,
    resample_linear,
)


log = logging.getLogger("extnded_thotz")


class TranscriptionError(RuntimeError):
    """Transcription failed (model load, decode, or network error)."""


def _model_cache_dir(model_size: str) -> Path | None:
    """Hugging Face cache folder holding the downloaded model, if we can name it."""
    try:
        from faster_whisper.utils import _MODELS
        from huggingface_hub.constants import HF_HUB_CACHE
    except Exception:
        return None
    repo_id = _MODELS.get(model_size, model_size)
    if "/" not in repo_id:
        return None
    return Path(HF_HUB_CACHE) / f"models--{repo_id.replace('/', '--')}"


class LocalWhisperBackend:
    name = "local"

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
        self._use_vad = False
        self._lock = threading.Lock()
        self._recovered = False  # cache repair is attempted at most once

    def _open(self):
        from faster_whisper import WhisperModel

        # VAD stays off: push-to-talk already bounds the audio, VAD eats short
        # utterances (observed removing a full 1.15s dictation), and its
        # onnxruntime dep crashes PyInstaller analysis on Python 3.14.
        self._use_vad = False
        return WhisperModel(self.model_size, device="cpu", compute_type="int8")

    def load(self):
        with self._lock:
            if self._model is not None:
                return self
            try:
                self._model = self._open()
                self._recovered = False  # a fresh model may repair the cache again
            except ImportError as exc:
                raise TranscriptionError("faster-whisper is not installed") from exc
            except Exception as exc:
                if not self._reset_corrupt_cache(exc):
                    raise TranscriptionError(
                        f"Could not load the local '{self.model_size}' model: {exc}"
                    ) from exc
                try:
                    self._model = self._open()
                    self._recovered = False
                except Exception as retry_exc:
                    raise TranscriptionError(
                        f"Could not load the local '{self.model_size}' model: {retry_exc}"
                    ) from retry_exc
        return self

    def _reset_corrupt_cache(self, cause) -> bool:
        """Drop a cached model that CTranslate2 refuses to open.

        An interrupted download leaves a model.bin CTranslate2 cannot parse
        ("Invalid string length in model.bin") and nothing else ever repairs it,
        so dictation stays broken until the cache is cleared by hand. Removing
        the folder makes faster-whisper fetch a clean copy on the retry.
        """
        if self._recovered:
            return False
        self._recovered = True
        folder = _model_cache_dir(self.model_size)
        if folder is None or not folder.is_dir():
            return False
        try:
            shutil.rmtree(folder)
        except OSError as exc:
            log.warning("Could not clear cached model %s: %s", folder, exc)
            return False
        log.warning(
            "Local model '%s' failed to load (%s) — cleared the cached copy, downloading it again",
            self.model_size, cause,
        )
        return True

    def transcribe(self, audio, language=None) -> str:
        if audio.size < TARGET_RATE // 10:  # under 0.1 s of audio
            return ""
        if is_unusable(audio):
            # Muted/dead/corrupt input: Whisper confidently invents filler
            # ("You") on digital silence — never hand it such audio.
            return ""
        self.load()
        try:
            return self._decode(audio, language)
        except Exception as exc:
            # A loaded model keeps reading model.bin lazily, so a cache that is
            # rewritten underneath it (another run repairing/re-downloading, an
            # interrupted download) poisons every later dictation. Rebuild once
            # rather than staying broken until the app is restarted.
            if not self._reload_after_failure(exc):
                raise TranscriptionError(str(exc)) from exc
        try:
            return self._decode(audio, language)
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc

    def _decode(self, audio, language=None) -> str:
        segments, _info = self._model.transcribe(
            audio, language=language, beam_size=5, vad_filter=self._use_vad,
            # Conditioning on prior text lets a filler hallucination ("You")
            # self-reinforce across segments — off for push-to-talk clips.
            condition_on_previous_text=False,
        )
        # Hallucination guard: on quiet/dead input Whisper confidently
        # invents filler ("You", "Thanks for watching…"). Discard rule
        # from OpenAI's reference pipeline: drop a segment only when
        # no_speech_prob > 0.6 AND avg_logprob < -1.0. If everything is
        # dropped the result is "" and the app reports "nothing heard".
        parts = (
            seg.text.strip()
            for seg in segments
            if not (seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0)
        )
        return " ".join(part for part in parts if part).strip()

    def _reload_after_failure(self, cause) -> bool:
        """Drop a model that broke mid-use and reload it; False if hopeless."""
        with self._lock:
            if self._model is None:  # never loaded, so nothing to rebuild
                return False
            self._model = None
        log.warning(
            "Local model '%s' failed after loading (%s) — rebuilding it",
            self.model_size, cause,
        )
        try:
            self.load()
        except TranscriptionError as exc:
            log.error("Model rebuild failed: %s", exc)
            return False
        return True


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
        if is_unusable(audio):
            return ""
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
