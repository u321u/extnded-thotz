"""Floating status overlay shown while recording and processing."""

import random
import time
import tkinter as tk


def _animations_enabled() -> bool:
    """Honor Windows' 'Show animations in Windows' accessibility setting."""
    try:
        import ctypes

        enabled = ctypes.c_int()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x1042,  # SPI_GETCLIENTAREAANIMATION
            0,
            ctypes.byref(enabled),
            0,
        )
        return bool(ok and enabled.value)
    except Exception:
        return True


class Overlay:
    WIDTH = 300
    HEIGHT = 72

    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.94)
        except tk.TclError:
            pass
        self.win.configure(bg="#020804")
        self.canvas = tk.Canvas(
            self.win,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg="#020804",
            highlightthickness=1,
            highlightbackground="#0b5f2a",
        )
        self.canvas.pack(fill="both", expand=True)
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        self.win.geometry(
            f"{self.WIDTH}x{self.HEIGHT}"
            f"+{(screen_w - self.WIDTH) // 2}+{screen_h - 150}"
        )
        self._flash_job = None
        self._matrix_job = None
        self._level_provider = lambda: 0.0
        self._animate = _animations_enabled()
        self._column_width = 14
        self._drops = [
            random.uniform(-self.HEIGHT, self.HEIGHT)
            for _ in range(max(1, self.WIDTH // self._column_width))
        ]
        self._last_frame = time.monotonic()
        self.win.withdraw()

    def show(self, text: str, fg: str = "#ff5c5c") -> None:
        self._stop_matrix()
        self._cancel_flash()
        self.canvas.delete("all")
        self.canvas.create_text(
            self.WIDTH / 2,
            self.HEIGHT / 2,
            text=text,
            fill=fg,
            font=("Segoe UI", 10, "bold"),
        )
        self.win.deiconify()
        self.win.lift()

    def listen(self, level_provider=None) -> None:
        """Show the mic-reactive Matrix listening state."""
        self._cancel_flash()
        self._stop_matrix()
        self._level_provider = level_provider or (lambda: 0.0)
        self.win.deiconify()
        self.win.lift()
        self._last_frame = time.monotonic()
        self._draw_matrix()

    def hide(self) -> None:
        self._stop_matrix()
        self._cancel_flash()
        self.win.withdraw()

    def flash(self, text: str, fg: str = "#ffb3b3", ms: int = 1200) -> None:
        self.show(text, fg)
        self._flash_job = self.root.after(ms, self.hide)

    def _cancel_flash(self) -> None:
        if self._flash_job is not None:
            try:
                self.root.after_cancel(self._flash_job)
            except Exception:
                pass
            self._flash_job = None

    def _draw_matrix(self) -> None:
        self._matrix_job = None
        if not self.win.winfo_viewable():
            return
        now = time.monotonic()
        elapsed = min(0.1, now - self._last_frame)
        self._last_frame = now
        try:
            level = max(0.0, min(1.0, float(self._level_provider())))
        except Exception:
            level = 0.0

        self.canvas.delete("all")
        glyphs = "01THOTZSCOUTGOAT"
        speed = 35 + level * 150
        for index, y in enumerate(self._drops):
            x = index * self._column_width + (self._column_width / 2)
            y += speed * elapsed * (0.65 + (index % 5) * 0.12)
            if y > self.HEIGHT + 45:
                y = random.uniform(-75, -15)
            self._drops[index] = y
            for trail in range(4):
                char_y = y - trail * 15
                if -15 <= char_y <= self.HEIGHT + 15:
                    color = ("#b8ffd0", "#37e66d", "#128a3d", "#075523")[trail]
                    self.canvas.create_text(
                        x,
                        char_y,
                        text=random.choice(glyphs),
                        fill=color,
                        font=("Consolas", 8, "bold"),
                    )

        glow = int(95 + level * 160)
        accent = f"#00{glow:02x}{min(255, 70 + glow // 2):02x}"
        self.canvas.create_rectangle(
            32,
            14,
            self.WIDTH - 32,
            58,
            fill="#020804",
            outline=accent,
            width=1,
        )
        self.canvas.create_text(
            self.WIDTH / 2,
            29,
            text="THOTZ BY SCOUT GOAT",
            fill="#b8ffd0",
            font=("Consolas", 10, "bold"),
        )
        bars = "▮" * max(1, round(1 + level * 8))
        self.canvas.create_text(
            self.WIDTH / 2,
            45,
            text=f"{bars}  LISTENING",
            fill=accent,
            font=("Consolas", 8, "bold"),
        )
        if self._animate:
            self._matrix_job = self.root.after(65, self._draw_matrix)

    def _stop_matrix(self) -> None:
        if self._matrix_job is not None:
            try:
                self.root.after_cancel(self._matrix_job)
            except Exception:
                pass
            self._matrix_job = None
