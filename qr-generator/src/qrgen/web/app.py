"""Flask web app for qrgen.

Run locally:   python -m qrgen.web
Production:    gunicorn "qrgen.web.app:create_app()"
"""

from __future__ import annotations

import argparse
import io
import math
from typing import Any, Dict, Tuple

from flask import Flask, Response, jsonify, render_template, request

from .. import payloads
from ..render import Style, build_matrix, contrast_warning, to_png, to_svg, version_of

MAX_FIELD_CHARS = 4000
MIN_SIZE, MAX_SIZE = 64, 4096


def _parse(data: Any) -> Tuple[str, Style, int]:
    """Validate a request body. Returns (payload text, style, minimum PNG size)."""
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object.")

    fields = data.get("fields") or {}
    if not isinstance(fields, dict):
        raise ValueError("'fields' must be an object.")
    for key, value in fields.items():
        if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
            raise ValueError(f"The '{key}' field is too long (limit {MAX_FIELD_CHARS} characters).")

    payload = payloads.build(str(data.get("kind", "")), fields)

    raw = data.get("style") or {}
    if not isinstance(raw, dict):
        raise ValueError("'style' must be an object.")
    try:
        border = int(raw.get("border", 4))
        size = int(data.get("size", 1024))
    except (TypeError, ValueError):
        raise ValueError("Border and size must be whole numbers.") from None
    style = Style(
        fg=str(raw.get("fg", "#000000")),
        bg=str(raw.get("bg", "#ffffff")),
        shape=str(raw.get("shape", "square")),
        border=border,
        ec=str(raw.get("ec", "M")),
    ).validated()
    if not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError(f"Size must be between {MIN_SIZE} and {MAX_SIZE} pixels.")
    return payload, style, size


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/generate")
    def generate():
        try:
            payload, style, size = _parse(request.get_json(silent=True))
            matrix = build_matrix(payload, style.ec)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        n = len(matrix)
        dim = n + 2 * style.border
        return jsonify(
            payload=payload,
            svg=to_svg(matrix, style, 300),
            version=version_of(matrix),
            modules=n,
            bytes=len(payload.encode("utf-8")),
            png_px=dim * max(1, math.ceil(size / dim)),
            warning=contrast_warning(style),
        )

    @app.post("/api/download")
    def download():
        body = request.get_json(silent=True)
        fmt = str(body.get("format", "png")).lower() if isinstance(body, dict) else ""
        if fmt not in ("png", "svg"):
            return jsonify(error="Format must be png or svg."), 400
        try:
            payload, style, size = _parse(body)
            matrix = build_matrix(payload, style.ec)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        kind = "".join(ch for ch in str(body.get("kind", "code")) if ch.isalnum()) or "code"
        filename = f"qr-{kind}.{fmt}"
        if fmt == "svg":
            data, mimetype = to_svg(matrix, style, size).encode("utf-8"), "image/svg+xml"
        else:
            buf = io.BytesIO()
            to_png(matrix, style, size).save(buf, format="PNG")
            data, mimetype = buf.getvalue(), "image/png"
        return Response(
            data,
            mimetype=mimetype,
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
        )

    @app.errorhandler(413)
    def too_big(_exc):
        return jsonify(error="Request is too large."), 413

    @app.after_request
    def security_headers(resp: Response) -> Response:
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    return app


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="qrgen-web", description="Run the qrgen web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Address to listen on (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=5000, help="Port (default 5000).")
    args = parser.parse_args(argv)
    create_app().run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
