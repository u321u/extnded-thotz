import time
import types

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


# -- mic probe ---------------------------------------------------------------
# Mimics the machine layout where the bug bit: default MME mic is dead, the
# live mic is behind WDM-KS, and a loud loopback endpoint ("Stereo Mix") sits
# there too. The fake InputStream is callback-only on purpose — PortAudio's
# blocking read() is unsupported on WDM-KS, so a probe that calls read()
# silently skips every device on that host.


def _fake_sd(default: int, signals: dict[int, float]):
    devices = [
        {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 1,
         "default_samplerate": 44100, "hostapi": 0},
        {"name": "Microphone Array (AMD Audio Dev", "max_input_channels": 1,
         "default_samplerate": 44100, "hostapi": 0},
        {"name": "Stereo Mix (Realtek HD Audio Stereo input)", "max_input_channels": 1,
         "default_samplerate": 48000, "hostapi": 2},
        {"name": "Microphone (Realtek HD Audio Mic input)", "max_input_channels": 1,
         "default_samplerate": 44100, "hostapi": 2},
        {"name": "Microphone Array (AMDAfdInstall Wave Microphone - 0)",
         "max_input_channels": 1, "default_samplerate": 48000, "hostapi": 2},
    ]
    host_names = ["MME", "Windows WASAPI", "Windows WDM-KS"]

    class InputStream:
        def __init__(self, device=None, samplerate=None, channels=1,
                     dtype=None, callback=None, **_kw):
            if device not in signals:
                raise RuntimeError(f"device {device} unavailable")
            self._peak = signals[device]
            self._callback = callback

        def __enter__(self):
            block = np.full((64, 1), self._peak, dtype=np.float32)
            for _ in range(3):
                self._callback(block, 64, None, None)
            return self

        def __exit__(self, *exc):
            return False

        def start(self):
            pass

    def query_devices(kind=None):
        if isinstance(kind, int):
            return devices[kind]
        if kind == "input":
            return [d for d in devices if d["max_input_channels"] > 0] or None
        return devices

    return types.SimpleNamespace(
        devices=devices,
        default=types.SimpleNamespace(device=[default, -1]),
        InputStream=InputStream,
        query_devices=query_devices,
        query_hostapis=lambda index: {"name": host_names[index]},
    )


def _probe_recorder(**kw) -> Recorder:
    rec = Recorder()
    rec.PROBE_SECONDS = 0.05  # keep the test snappy
    for key, value in kw.items():
        setattr(rec, key, value)
    return rec


def test_probe_skips_dead_default_and_finds_wdmks_mic():
    """The default MME mic reads digital silence; the live mic is WDM-KS."""
    sd = _fake_sd(default=1, signals={1: 1e-5, 4: 0.12})
    rec = _probe_recorder()
    assert rec.probe_working_device(sd=sd) == 4
    assert rec._preferred_device == 4


def test_probe_prefers_voice_endpoint_over_loud_loopback():
    """Stereo Mix carries loud system audio — never dictation input."""
    sd = _fake_sd(default=1, signals={1: 1e-5, 3: 0.005, 2: 0.5})
    rec = _probe_recorder()
    assert rec.probe_working_device(sd=sd) == 3


def test_probe_respects_pinned_name_over_louder_unpinned():
    sd = _fake_sd(default=1, signals={1: 1e-5, 2: 0.5, 3: 0.005, 4: 0.0})
    rec = _probe_recorder(_preferred_name="realtek")
    # both "Stereo Mix (Realtek…)" and "Microphone (Realtek…)" match, but
    # only the mic endpoint is a voice device
    assert rec.probe_working_device(sd=sd) == 3


def test_probe_returns_none_when_everything_is_silent_or_corrupt():
    sd = _fake_sd(default=1, signals={1: 1e-5, 3: 9.0, 4: 0.0})
    rec = _probe_recorder()
    assert rec.probe_working_device(sd=sd) is None
    assert rec._preferred_device is None
