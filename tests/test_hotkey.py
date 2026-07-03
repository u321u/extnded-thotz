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
