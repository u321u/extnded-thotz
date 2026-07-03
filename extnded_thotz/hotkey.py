"""Push-to-talk / toggle hotkey handling.

HotkeyController is a pure state machine (unit-testable, no OS hooks).
KeyboardBinder wires it to the `keyboard` library's global hooks and also
listens for ESC to cancel an in-flight recording.
"""

import time


KEY_ALIASES = {
    "control": "ctrl",
    "left control": "left ctrl",
    "right control": "right ctrl",
    "escape": "esc",
    "return": "enter",
    "prior": "page up",
    "next": "page down",
}
MODIFIERS = {
    "ctrl", "left ctrl", "right ctrl",
    "shift", "left shift", "right shift",
    "alt", "left alt", "right alt",
    "windows", "left windows", "right windows",
}


def normalize_key_name(name: str) -> str:
    key = " ".join(str(name).strip().lower().replace("_", " ").split())
    return KEY_ALIASES.get(key, key)


def normalize_shortcut(shortcut: str) -> str:
    """Return a stable keyboard-library shortcut string or raise ValueError."""
    parts = [normalize_key_name(part) for part in str(shortcut).split("+")]
    if not parts or any(not part for part in parts):
        raise ValueError("Enter a shortcut such as right ctrl, F9, or ctrl+shift+space.")
    if len(parts) > 4:
        raise ValueError("Shortcuts can contain at most four keys.")
    if len(set(parts)) != len(parts):
        raise ValueError("A shortcut cannot contain the same key twice.")
    if "esc" in parts:
        raise ValueError("Esc is reserved for cancelling a recording.")
    for part in parts:
        if not all(char.isalnum() or char in " -" for char in part):
            raise ValueError(f"Unsupported key name: {part}")
    modifiers = [part for part in parts if part in MODIFIERS]
    keys = [part for part in parts if part not in MODIFIERS]
    return "+".join(modifiers + keys)


def shortcut_parts(shortcut: str) -> tuple[str, ...]:
    return tuple(normalize_shortcut(shortcut).split("+"))


def _part_is_pressed(part: str, pressed: set[str]) -> bool:
    if part in pressed:
        return True
    if part in {"ctrl", "shift", "alt", "windows"}:
        return any(key == part or key.endswith(f" {part}") for key in pressed)
    return False


class ShortcutState:
    """Tracks a possibly multi-key shortcut from raw keyboard events."""

    def __init__(self, shortcut: str):
        self.parts = shortcut_parts(shortcut)
        self.pressed: set[str] = set()
        self.active = False

    def feed(self, name: str, event_type: str) -> str | None:
        key = normalize_key_name(name)
        if event_type == "down":
            self.pressed.add(key)
        elif event_type == "up":
            self.pressed.discard(key)
        else:
            return None
        now_active = all(_part_is_pressed(part, self.pressed) for part in self.parts)
        if now_active and not self.active:
            self.active = True
            return "press"
        if self.active and not now_active:
            self.active = False
            return "release"
        return None


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
        self.key = normalize_shortcut(key)
        self._handles = []
        self._state = ShortcutState(self.key)

    def bind(self) -> None:
        import keyboard

        self._state = ShortcutState(self.key)
        self._handles = [keyboard.hook(self._on_event, suppress=False)]

    def _on_event(self, event) -> None:
        if event.event_type == "down" and normalize_key_name(event.name) == "esc":
            self.controller.cancel()
        transition = self._state.feed(event.name, event.event_type)
        if transition == "press":
            self.controller.press()
        elif transition == "release":
            self.controller.release()

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
        self.key = normalize_shortcut(new_key)
        self.bind()
