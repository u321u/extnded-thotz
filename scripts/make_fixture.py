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
