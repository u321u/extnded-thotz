"""Settings window. Runs as its own process so the tray app's Tk loop and
this window never share a thread: python -m extnded_thotz.settings_ui"""

import sys

import tkinter as tk
from tkinter import messagebox, ttk

from . import APP_DISPLAY_NAME, config as config_mod
from .hotkey import MODIFIERS, normalize_key_name, normalize_shortcut

BG = "#111111"
FG = "#f2f2f2"

MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]


def input_device_choices() -> list[str]:
    """"auto" plus every input device name currently visible to Windows."""
    try:
        import sounddevice as sd

        names = sorted(
            {d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0}
        )
        return ["auto"] + names
    except Exception:
        return ["auto"]

TK_KEY_NAMES = {
    "Control_L": "left ctrl",
    "Control_R": "right ctrl",
    "Shift_L": "left shift",
    "Shift_R": "right shift",
    "Alt_L": "left alt",
    "Alt_R": "right alt",
    "Meta_L": "left cmd" if sys.platform == "darwin" else "left windows",
    "Meta_R": "right cmd" if sys.platform == "darwin" else "right windows",
    "Win_L": "left cmd" if sys.platform == "darwin" else "left windows",
    "Win_R": "right cmd" if sys.platform == "darwin" else "right windows",
    "space": "space",
    "Return": "enter",
    "Escape": "esc",
}


def main() -> None:
    cfg = config_mod.load_config()
    root = tk.Tk()
    root.title(f"{APP_DISPLAY_NAME} — Settings")
    root.configure(bg=BG)
    root.resizable(False, False)

    hotkey_var = tk.StringVar(value=cfg["hotkey"])
    mode_var = tk.StringVar(value=cfg["mode"])
    backend_var = tk.StringVar(value=cfg["backend"])
    model_var = tk.StringVar(value=cfg["model_size"])
    device_var = tk.StringVar(value=cfg.get("input_device") or "auto")
    language_var = tk.StringVar(value=cfg["language"] or "")
    llm_var = tk.StringVar(value=cfg["llm_cleanup"])
    injection_var = tk.StringVar(value=cfg["injection"])
    api_key_var = tk.StringVar(value=cfg["openai_api_key"])
    fillers_var = tk.BooleanVar(value=cfg["remove_fillers"])
    commands_var = tk.BooleanVar(value=cfg["voice_commands"])
    restore_var = tk.BooleanVar(value=cfg["restore_clipboard"])
    overlay_var = tk.BooleanVar(value=cfg["show_overlay"])
    space_var = tk.BooleanVar(value=cfg["append_space"])

    body = tk.Frame(root, bg=BG, padx=16, pady=12)
    body.pack(fill="both", expand=True)
    row = 0

    def label(text):
        tk.Label(body, text=text, bg=BG, fg=FG, anchor="w").grid(
            row=row, column=0, sticky="w", pady=3, padx=(0, 10)
        )

    def combo(var, values):
        nonlocal row
        box = ttk.Combobox(body, textvariable=var, values=values, state="readonly", width=22)
        box.grid(row=row, column=1, sticky="we", pady=3)
        row += 1

    def check(text, var):
        nonlocal row
        tk.Checkbutton(
            body, text=text, variable=var, bg=BG, fg=FG,
            activebackground=BG, activeforeground=FG, selectcolor="#222222", anchor="w",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=1)
        row += 1

    label("Dictation shortcut")
    shortcut_frame = tk.Frame(body, bg=BG)
    shortcut_frame.grid(row=row, column=1, sticky="we", pady=3)
    shortcut_entry = tk.Entry(
        shortcut_frame,
        textvariable=hotkey_var,
        width=17,
        bg="#222222",
        fg=FG,
        insertbackground=FG,
    )
    shortcut_entry.pack(side="left", fill="x", expand=True)
    capture_button = tk.Button(
        shortcut_frame,
        text="Record…",
        bg="#222222",
        fg=FG,
        activebackground="#333333",
        activeforeground=FG,
        width=8,
    )
    capture_button.pack(side="left", padx=(6, 0))
    row += 1
    tk.Label(
        body,
        text="Type a shortcut or click Record, then press it.",
        bg=BG,
        fg="#a8a8a8",
        anchor="w",
        font=("Segoe UI", 8),
    ).grid(row=row, column=1, sticky="w", pady=(0, 4))
    row += 1

    captured_keys = []
    capture_bindings = []

    def stop_capture(value=None):
        for sequence, binding_id in capture_bindings:
            root.unbind(sequence, binding_id)
        capture_bindings.clear()
        if value:
            hotkey_var.set(normalize_shortcut("+".join(captured_keys)))
        capture_button.config(text="Record…")
        shortcut_entry.focus_set()

    def capture_press(event):
        key = normalize_key_name(TK_KEY_NAMES.get(event.keysym, event.keysym))
        if key == "esc":
            stop_capture()
            return "break"
        if key not in captured_keys:
            captured_keys.append(key)
        capture_button.config(text="Press…")
        if key not in MODIFIERS:
            stop_capture(key)
        return "break"

    def capture_release(event):
        key = normalize_key_name(TK_KEY_NAMES.get(event.keysym, event.keysym))
        if (
            captured_keys
            and all(item in MODIFIERS for item in captured_keys)
            and key in captured_keys
        ):
            stop_capture(key)
        return "break"

    def start_capture():
        if capture_bindings:
            stop_capture()
        captured_keys.clear()
        capture_button.config(text="Press…")
        shortcut_entry.focus_set()
        capture_bindings.extend(
            [
                ("<KeyPress>", root.bind("<KeyPress>", capture_press)),
                ("<KeyRelease>", root.bind("<KeyRelease>", capture_release)),
            ]
        )

    capture_button.config(command=start_capture)
    label("Key mode"); combo(mode_var, ["hold", "toggle"])
    label("Transcription backend"); combo(backend_var, ["auto", "local", "openai"])
    label("Local model size"); combo(model_var, MODEL_CHOICES)
    label("Microphone"); combo(device_var, input_device_choices())
    label("Language (blank = auto)")
    entry = tk.Entry(body, textvariable=language_var, width=24, bg="#222222", fg=FG,
                     insertbackground=FG)
    entry.grid(row=row, column=1, sticky="we", pady=3); row += 1
    label("AI polish (needs API key)"); combo(llm_var, ["auto", "on", "off"])
    label("Insert method"); combo(injection_var, ["paste", "type"])
    label("OpenAI API key (optional)")
    key_entry = tk.Entry(body, textvariable=api_key_var, width=24, show="•",
                         bg="#222222", fg=FG, insertbackground=FG)
    key_entry.grid(row=row, column=1, sticky="we", pady=3); row += 1

    check("Remove filler words (um, uh…)", fillers_var)
    check('Voice commands ("new line", "new paragraph")', commands_var)
    check("Restore clipboard after paste", restore_var)
    check("Show status pill while dictating", overlay_var)
    check("Append trailing space after insert", space_var)

    def save() -> None:
        try:
            hotkey = normalize_shortcut(hotkey_var.get())
        except ValueError as exc:
            messagebox.showerror(APP_DISPLAY_NAME, str(exc))
            shortcut_entry.focus_set()
            return
        cfg.update(
            hotkey=hotkey, mode=mode_var.get(), backend=backend_var.get(),
            model_size=model_var.get(), language=(language_var.get().strip() or None),
            input_device=("" if device_var.get() == "auto" else device_var.get()),
            llm_cleanup=llm_var.get(), injection=injection_var.get(),
            openai_api_key=api_key_var.get().strip(),
            remove_fillers=fillers_var.get(), voice_commands=commands_var.get(),
            restore_clipboard=restore_var.get(), show_overlay=overlay_var.get(),
            append_space=space_var.get(),
        )
        config_mod.save_config(cfg)
        messagebox.showinfo(APP_DISPLAY_NAME, "Saved. The running app picks this up within ~2 seconds.")
        root.destroy()

    buttons = tk.Frame(body, bg=BG)
    buttons.grid(row=row, column=0, columnspan=2, pady=(12, 0), sticky="e")
    tk.Button(buttons, text="Cancel", command=root.destroy, bg="#222222", fg=FG,
              activebackground="#333333", activeforeground=FG, width=10).pack(side="left", padx=6)
    tk.Button(buttons, text="Save", command=save, bg="#2e7d32", fg="white",
              activebackground="#388e3c", activeforeground="white", width=10).pack(side="left")

    root.mainloop()


if __name__ == "__main__":
    main()
