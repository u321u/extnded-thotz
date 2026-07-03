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
        self._use_vad = False
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise TranscriptionError("faster-whisper is not installed") from exc
                # VAD stays off: push-to-talk already bounds the audio, VAD eats
                # short utterances (observed removing a full 1.15s dictation), and
                # its onnxruntime dep crashes PyInstaller analysis on Python 3.14.
                self._use_vad = False
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self

    def transcribe(self, audio, language=None) -> str:
        if audio.size < TARGET_RATE // 10:  # under 0.1 s of audio
            return ""
        self.load()
        try:
            segments, _info = self._model.transcribe(
                audio, language=language, beam_size=5, vad_filter=self._use_vad
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
