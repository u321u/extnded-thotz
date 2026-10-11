from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, send_file

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)


def _send(path: Path):
    if not path.is_file():
        abort(404)
    return send_file(path)


@app.get("/")
def index():
    return _send(BASE_DIR / "index.html")


@app.get("/download")
def download_page():
    return _send(BASE_DIR / "download.html")


@app.get("/faq")
def faq_page():
    return _send(BASE_DIR / "faq.html")


@app.get("/pricing")
def pricing_page():
    return _send(BASE_DIR / "pricing.html")


@app.get("/styles.css")
def styles():
    return _send(BASE_DIR / "styles.css")


@app.get("/script.js")
def script():
    return _send(BASE_DIR / "script.js")


@app.get("/assets/<path:name>")
def assets(name: str):
    return _send(BASE_DIR / "assets" / name)


@app.get("/downloads/<path:name>")
def downloads(name: str):
    return _send(BASE_DIR / "public" / "downloads" / name)


@app.get("/<path:name>")
def fallback(name: str):
    target = BASE_DIR / name
    if target.is_file():
        return _send(target)
    abort(404)


@app.errorhandler(404)
def not_found(_e):
    return _send(BASE_DIR / "404.html"), 404
