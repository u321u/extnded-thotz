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
