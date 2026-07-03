"""System tray icon built from the Extnded Thotz goat logo."""

from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


def load_logo_image(size: int = 64, recording: bool = False):
    from PIL import Image, ImageDraw

    logo = ASSET_DIR / "logo.png"
    if logo.exists():
        img = Image.open(logo).convert("RGBA").resize((size, size), Image.LANCZOS)
    else:  # fallback glyph if the asset is missing
        img = Image.new("RGBA", (size, size), (11, 11, 11, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([size * 0.3, size * 0.15, size * 0.7, size * 0.6], fill="white")
        draw.rectangle([size * 0.45, size * 0.6, size * 0.55, size * 0.85], fill="white")
    if recording:
        draw = ImageDraw.Draw(img)
        r = size // 5
        draw.ellipse([size - 2 * r - 2, size - 2 * r - 2, size - 2, size - 2],
                     fill=(230, 60, 60, 255))
    return img


def build_tray(app):
    import pystray
    from pystray import Menu, MenuItem as Item

    menu = Menu(
        Item("Extnded Thotz", None, enabled=False),
        Item("Enabled", lambda icon, item: _toggle_enabled(app),
             checked=lambda item: app.enabled),
        Item("Copy last transcript", lambda icon, item: app.copy_last()),
        Item("Settings…", lambda icon, item: app.open_settings()),
        Item("Quit", lambda icon, item: app.quit()),
    )
    return pystray.Icon("extnded_thotz", load_logo_image(),
                        "Extnded Thotz — dictation", menu)


def _toggle_enabled(app):
    app.enabled = not app.enabled
