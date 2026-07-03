import json

from extnded_thotz import config


def test_defaults_offline_first():
    cfg = config.load_config(path="Z:/does/not/exist.json")
    assert cfg["backend"] == "auto"
    assert cfg["model_size"] == "base"
    assert cfg["hotkey"] == "ctrl+windows"
    assert cfg["mode"] == "hold"
    assert cfg["injection"] == "paste"


def test_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = config.load_config(path=p)
    cfg["hotkey"] = "f9"
    cfg["mode"] = "toggle"
    config.save_config(cfg, path=p)
    again = config.load_config(path=p)
    assert again["hotkey"] == "f9"
    assert again["mode"] == "toggle"


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    assert config.load_config(path=p) == dict(config.DEFAULTS)


def test_unknown_keys_dropped(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"hotkey": "f8", "evil": 1}), encoding="utf-8")
    cfg = config.load_config(path=p)
    assert cfg["hotkey"] == "f8"
    assert "evil" not in cfg


def test_resolve_api_key_env_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    assert config.resolve_api_key({"openai_api_key": ""}) == "sk-env"
    assert config.resolve_api_key({"openai_api_key": "sk-cfg"}) == "sk-cfg"
    monkeypatch.delenv("OPENAI_API_KEY")
    assert config.resolve_api_key({"openai_api_key": ""}) == ""
