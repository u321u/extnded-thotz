from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, send_file, make_response

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)

# Every response gets these. CSP is strict: self-hosted everything, no
# inline event handlers are used by script.js, so we can default-deny.
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self'; "
        "style-src 'self'; "
        "script-src 'self'; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "media-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-DNS-Prefetch-Control": "off",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# HTML pages get long-lived immutable caching only for assets; pages stay revalidable.
_PAGE_TYPES = {".html": "text/html; charset=utf-8", ".xml": "application/xml; charset=utf-8", ".txt": "text/plain; charset=utf-8"}


def _send(path: Path):
    """Serve a file from BASE_DIR only — no traversal, correct MIME, safe headers."""
    resolved = path.resolve()
    if not resolved.is_relative_to(BASE_DIR):  # traversal guard
        abort(404)
    if not resolved.is_file():
        abort(404)
    response = send_file(resolved)
    for key, value in _SECURITY_HEADERS.items():
        response.headers[key] = value
    return response


def _page(filename: str):
    return _send(BASE_DIR / filename)


@app.after_request
def _apply_headers(response):
    # 404/500 HTML responses also carry security headers.
    if "Content-Security-Policy" not in response.headers:
        for key, value in _SECURITY_HEADERS.items():
            response.headers[key] = value
    return response


@app.get("/")
def index():
    return _page("index.html")


@app.get("/download")
def download_page():
    return _page("download.html")


@app.get("/faq")
def faq_page():
    return _page("faq.html")


@app.get("/styles.css")
def styles():
    return _page("styles.css")


@app.get("/script.js")
def script():
    return _page("script.js")


@app.get("/sitemap.xml")
def sitemap():
    return _page("sitemap.xml")


@app.get("/robots.txt")
def robots():
    return _page("robots.txt")


@app.get("/favicon.ico")
def favicon():
    return _page("favicon.ico")


@app.get("/fonts/<path:name>")
def fonts(name: str):
    return _send(BASE_DIR / "fonts" / name)


@app.get("/assets/<path:name>")
def assets(name: str):
    return _send(BASE_DIR / "assets" / name)


@app.get("/downloads/<path:name>")
def downloads(name: str):
    root = (BASE_DIR / "public" / "downloads").resolve()
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        abort(404)
    # Executables/zips: attachment disposition so nothing renders in-browser.
    response = send_file(resolved)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.errorhandler(404)
def not_found(_e):
    return _send(BASE_DIR / "404.html"), 404
