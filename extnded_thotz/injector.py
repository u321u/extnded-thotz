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
