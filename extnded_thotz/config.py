"""Settings persistence: %APPDATA%\\ExtndedThotz\\config.json with safe defaults."""

import json
import os
from pathlib import Path

APP_NAME = "ExtndedThotz"

DEFAULTS = {
    "hotkey": "ctrl+windows",   # key chord held (or toggled) to dictate
    "mode": "hold",             # hold | toggle
    "backend": "auto",          # auto (openai if key, else local) | local | openai
    "model_size": "base",       # faster-whisper: tiny|base|small|medium|large-v3
    "language": None,           # None = auto-detect, else ISO code like "en"
    "llm_cleanup": "auto",      # auto (on when key present) | on | off
    "remove_fillers": True,
    "voice_commands": True,     # "new line" / "new paragraph"
    "injection": "paste",       # paste | type
    "restore_clipboard": True,
    "append_space": False,
    "show_overlay": True,
    "preload_model": True,
    "openai_api_key": "",
    "openai_stt_model": "whisper-1",
    "openai_llm_model": "gpt-4o-mini",
}


def config_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home())
    return Path(root) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config(path=None) -> dict:
    p = Path(path) if path else config_path()
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return cfg
    if isinstance(data, dict):
        for key, value in data.items():
            if key in DEFAULTS:
                cfg[key] = value
    return cfg


def save_config(cfg: dict, path=None) -> None:
    p = Path(path) if path else config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    known = {k: cfg[k] for k in DEFAULTS if k in cfg}
    p.write_text(json.dumps(known, indent=2), encoding="utf-8")


def resolve_api_key(cfg: dict) -> str:
    return (cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()
