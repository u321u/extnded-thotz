"""Floating status pill shown while recording/processing. Main thread only."""

import tkinter as tk


class Overlay:
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        self.win.configure(bg="#0b0b0b")
        self.label = tk.Label(
            self.win, text="", fg="#ffffff", bg="#0b0b0b",
            font=("Segoe UI", 11, "bold"), padx=16, pady=7,
        )
        self.label.pack(fill="both", expand=True)
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        self.win.geometry(f"+{(screen_w - 200) // 2}+{screen_h - 130}")
        self._flash_job = None
        self.win.withdraw()

    def show(self, text: str, fg: str = "#ff5c5c") -> None:
        self._cancel_flash()
        self.label.config(text=text, fg=fg)
        self.win.deiconify()
        self.win.lift()

    def hide(self) -> None:
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
