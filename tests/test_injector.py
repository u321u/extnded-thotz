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
