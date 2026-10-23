import threading
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
    try:
        rec.start()
    except MicUnavailableError:
        return  # no working mic on this machine right now — raising is the contract
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
    try:
        rec.start()
    except MicUnavailableError:
        pytest.skip("mic not openable right now")
    time.sleep(0.1)
    rec.cancel()
    assert not rec.is_recording
    # stopping again returns empty rather than raising
    assert rec.stop().size == 0


def test_start_gives_up_when_the_audio_driver_never_answers(monkeypatch):
    """A wedged endpoint blocked the open forever and froze the hotkey thread."""
    rec = Recorder()
    rec.OPEN_TIMEOUT_S = 0.2
    gate = threading.Event()

    def stuck_open(sd, box):
        gate.wait(5)  # blocks exactly like PortAudio does on a dead driver

    monkeypatch.setattr(rec, "_open_input", stuck_open)
    try:
        with pytest.raises(MicUnavailableError, match="isn't responding"):
            rec.start()
        assert rec._wedged
    finally:
        gate.set()


def test_wedged_recorder_fails_fast_without_touching_audio_again(monkeypatch):
    rec = Recorder()
    rec._wedged = True
    rec._wedged_until = time.monotonic() + rec.RETRY_COOLDOWN_S

    def must_not_open(sd, box):
        raise AssertionError("must not call into the stuck audio driver again")

    monkeypatch.setattr(rec, "_open_input", must_not_open)
    with pytest.raises(MicUnavailableError, match="still recovering"):
        rec.start()


def test_timeout_poisons_the_device_that_blocked(monkeypatch):
    """Next attempt skips the endpoint that hung instead of blocking again."""
    rec = Recorder()
    rec.OPEN_TIMEOUT_S = 0.2
    gate = threading.Event()

    def stuck_open(sd, box):
        rec._opening_device = 7  # the candidate PortAudio is stuck inside
        gate.wait(5)

    monkeypatch.setattr(rec, "_open_input", stuck_open)
    try:
        with pytest.raises(MicUnavailableError, match="isn't responding"):
            rec.start()
        assert 7 in rec._poisoned
    finally:
        gate.set()


def test_recorder_retries_after_the_cooldown_elapses(monkeypatch):
    """A wedged audio stack recovers instead of breaking dictation for the session."""
    rec = Recorder()
    rec._wedged = True
    rec._wedged_until = time.monotonic() - 1  # cooldown already elapsed

    opened = {}

    def fake_open(sd, box):
        opened["called"] = True
        box["error"] = "still no device"

    monkeypatch.setattr(rec, "_open_input", fake_open)
    with pytest.raises(MicUnavailableError, match="Could not open microphone"):
        rec.start()
    assert opened.get("called") is True
    assert rec._wedged is False


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


class _StreamWithoutAudio:
    """Opens cleanly but never fires a callback (dead DirectSound mapper)."""

    def __init__(self, **kwargs):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


class _StreamWithAudio(_StreamWithoutAudio):
    def __init__(self, callback=None, **_kwargs):
        self._callback = callback

    def start(self):
        self._callback(np.full((64, 1), 0.1, dtype=np.float32), 64, None, None)


def _open_sd(default, dead: set[int]):
    """Fake sounddevice where `dead` devices open but deliver no frames."""
    names = [
        "Microsoft Sound Mapper - Input",
        "Microphone Array (AMD Audio Dev",
        "Stereo Mix (Realtek HD Audio Stereo input)",
        "Microphone (Realtek HD Audio Mic input)",
        "Microphone Array (AMDAfdInstall Wave Microphone - 0)",
    ]
    devices = [
        {"name": name, "max_input_channels": 1, "default_samplerate": 44100, "hostapi": 0}
        for name in names
    ]
    opened = []

    class InputStream:
        def __new__(cls, device=None, **kwargs):
            opened.append(device)
            return _StreamWithoutAudio(**kwargs) if device in dead else _StreamWithAudio(**kwargs)

    def query_devices(kind=None):
        if isinstance(kind, int):
            return devices[kind]
        return devices

    return types.SimpleNamespace(
        devices=devices,
        default=types.SimpleNamespace(device=[default, -1]),
        InputStream=InputStream,
        opened=opened,
        query_devices=query_devices,
        query_hostapis=lambda index: {"name": "MME"},
    )


def test_open_input_moves_past_an_endpoint_that_delivers_no_audio():
    rec = Recorder()
    sd = _open_sd(default=1, dead={1})
    box = {}
    rec._open_input(sd, box)
    assert sd.opened[0] == 1  # the OS default is attempted first
    assert rec._current_device != 1  # but it was rejected and the next tried
    assert "error" not in box


def test_open_input_stops_scanning_after_two_silent_endpoints():
    """Opening can block the interpreter, so never walk every silent endpoint."""
    rec = Recorder()
    sd = _open_sd(default=1, dead={0, 1, 2, 3, 4})
    box = {}
    rec._open_input(sd, box)
    assert len(sd.opened) <= rec.MAX_SILENT_DEVICES
    assert rec._current_device == sd.opened[-1]  # reported as "silent", not missing
    assert "error" not in box


def test_hung_endpoint_is_never_tried_again():
    rec = Recorder()
    rec._poisoned.add(1)
    sd = _open_sd(default=1, dead=set())
    rec._open_input(sd, {})
    assert 1 not in sd.opened


def test_probe_returns_none_when_everything_is_silent_or_corrupt():
    sd = _fake_sd(default=1, signals={1: 1e-5, 3: 9.0, 4: 0.0})
    rec = _probe_recorder()
    assert rec.probe_working_device(sd=sd) is None
    assert rec._preferred_device is None
