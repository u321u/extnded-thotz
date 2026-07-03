"""Push-to-talk / toggle hotkey handling.

HotkeyController is a pure state machine (unit-testable, no OS hooks).
KeyboardBinder wires it to the `keyboard` library's global hooks and also
listens for ESC to cancel an in-flight recording.
"""

import time


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
        self.key = key
        self._handles = []

    def bind(self) -> None:
        import keyboard

        self._handles = [
            keyboard.on_press_key(self.key, lambda e: self.controller.press(), suppress=False),
            keyboard.on_release_key(self.key, lambda e: self.controller.release(), suppress=False),
            keyboard.on_press_key("esc", lambda e: self.controller.cancel(), suppress=False),
        ]

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
        self.key = new_key
        self.bind()
