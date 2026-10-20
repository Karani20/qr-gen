"""Turn text into a QR matrix and draw it as PNG, SVG or terminal blocks."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import qrcode
from qrcode.exceptions import DataOverflowError
from PIL import Image, ImageDraw

Matrix = List[List[bool]]

EC_LEVELS = {
    "L": qrcode.constants.ERROR_CORRECT_L,  # about 7% recovery
    "M": qrcode.constants.ERROR_CORRECT_M,  # about 15%
    "Q": qrcode.constants.ERROR_CORRECT_Q,  # about 25%
    "H": qrcode.constants.ERROR_CORRECT_H,  # about 30%
}
SHAPES = ("square", "dots")
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class Style:
    fg: str = "#000000"
    bg: str = "#ffffff"
    shape: str = "square"
    border: int = 4  # quiet zone, in modules. The QR standard asks for 4.
    ec: str = "M"

    def validated(self) -> "Style":
        if self.ec not in EC_LEVELS:
            raise ValueError("Error correction must be one of L, M, Q, H.")
        if self.shape not in SHAPES:
            raise ValueError("Shape must be 'square' or 'dots'.")
        if not 0 <= self.border <= 20:
            raise ValueError("Border must be between 0 and 20 modules.")
        return Style(normalize_color(self.fg), normalize_color(self.bg), self.shape, self.border, self.ec)


def normalize_color(value: str) -> str:
    """Return #rrggbb for #rgb or #rrggbb input."""
    value = value.strip()
    if not _HEX.match(value):
        raise ValueError(f"Color must look like #112233 or #123, got {value!r}.")
    value = value.lower()
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return value


def _luminance(hex_color: str) -> float:
    channels = []
    for i in (1, 3, 5):
        v = int(hex_color[i : i + 2], 16) / 255
        channels.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = _luminance(normalize_color(fg)), _luminance(normalize_color(bg))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def contrast_warning(style: Style) -> str:
    """Return a warning when the colors are likely to scan badly, else ''."""
    style = style.validated()
    ratio = contrast_ratio(style.fg, style.bg)
    if ratio < 3:
        return f"Contrast is low ({ratio:.1f}:1). Many scanners will fail to read this."
    if _luminance(style.fg) > _luminance(style.bg):
        return "The code is lighter than its background. Some scanners cannot read inverted codes."
    return ""


def build_matrix(data: str, ec: str = "M") -> Matrix:
    """Encode data and return the module grid (True = dark), without a quiet zone."""
    if not data:
        raise ValueError("Nothing to encode.")
    if ec not in EC_LEVELS:
        raise ValueError("Error correction must be one of L, M, Q, H.")
    qr = qrcode.QRCode(version=None, error_correction=EC_LEVELS[ec], box_size=1, border=0)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except (DataOverflowError, ValueError) as exc:
        raise ValueError("Too much data for one QR code. Shorten it or lower the error correction.") from exc
    return qr.get_matrix()


def version_of(matrix: Matrix) -> int:
    return (len(matrix) - 17) // 4


def _runs(matrix: Matrix):
    """Yield (column, row, length) for each horizontal run of dark modules."""
    for r, row in enumerate(matrix):
        c, n = 0, len(row)
        while c < n:
            if row[c]:
                start = c
                while c < n and row[c]:
                    c += 1
                yield start, r, c - start
            else:
                c += 1


def _in_finder(r: int, c: int, n: int) -> bool:
    """True inside the three 7x7 corner eyes. Dots mode keeps these square so scanners lock on."""
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)


def to_svg(matrix: Matrix, style: Style, size: int = 1024) -> str:
    style = style.validated()
    n, q = len(matrix), style.border
    dim = n + 2 * q
    parts: List[str] = []
    if style.shape == "dots":
        for r, row in enumerate(matrix):
            for c, dark in enumerate(row):
                if not dark:
                    continue
                if _in_finder(r, c, n):
                    parts.append(f"M{c + q} {r + q}h1v1h-1z")
                else:
                    x, y = c + q + 0.5, r + q + 0.5
                    parts.append(f"M{x - 0.47:g} {y:g}a0.47 0.47 0 1 0 0.94 0a0.47 0.47 0 1 0 -0.94 0z")
    else:
        for c, r, length in _runs(matrix):
            parts.append(f"M{c + q} {r + q}h{length}v1h-{length}z")
    rendering = "" if style.shape == "dots" else ' shape-rendering="crispEdges"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
        f'width="{size}" height="{size}"{rendering}>'
        f'<rect width="{dim}" height="{dim}" fill="{style.bg}"/>'
        f'<path fill="{style.fg}" d="{"".join(parts)}"/></svg>\n'
    )


def to_png(matrix: Matrix, style: Style, min_size: int = 1024) -> Image.Image:
    """Draw a PNG at least min_size pixels wide, using whole pixels per module."""
    style = style.validated()
    n, q = len(matrix), style.border
    dim = n + 2 * q
    scale = max(1, math.ceil(min_size / dim))

    if style.shape == "dots":
        ss = 4  # supersample, then shrink for smooth circles
        big = Image.new("RGB", (dim * scale * ss, dim * scale * ss), style.bg)
        draw = ImageDraw.Draw(big)
        m = scale * ss
        inset = m * 0.03
        for r, row in enumerate(matrix):
            for c, dark in enumerate(row):
                if not dark:
                    continue
                x0, y0 = (c + q) * m, (r + q) * m
                if _in_finder(r, c, n):
                    draw.rectangle([x0, y0, x0 + m - 1, y0 + m - 1], fill=style.fg)
                else:
                    draw.ellipse([x0 + inset, y0 + inset, x0 + m - inset - 1, y0 + m - inset - 1], fill=style.fg)
        return big.resize((dim * scale, dim * scale), Image.LANCZOS)

    img = Image.new("RGB", (dim * scale, dim * scale), style.bg)
    draw = ImageDraw.Draw(img)
    for c, r, length in _runs(matrix):
        x0, y0 = (c + q) * scale, (r + q) * scale
        draw.rectangle([x0, y0, x0 + length * scale - 1, y0 + scale - 1], fill=style.fg)
    return img


def to_terminal(matrix: Matrix, border: int = 2, light_terminal: bool = False) -> str:
    """Block-character preview. Two module rows per text line.

    Default assumes a dark terminal, so light modules are drawn as blocks.
    """
    n = len(matrix)
    dim = n + 2 * border

    def dark(r: int, c: int) -> bool:
        r, c = r - border, c - border
        return 0 <= r < n and 0 <= c < n and matrix[r][c]

    ink = (lambda r, c: dark(r, c)) if light_terminal else (lambda r, c: not dark(r, c))
    lines = []
    for r in range(0, dim, 2):
        line = []
        for c in range(dim):
            top = ink(r, c)
            bottom = ink(r + 1, c) if r + 1 < dim else (not light_terminal)
            line.append("█" if top and bottom else "▀" if top else "▄" if bottom else " ")
        lines.append("".join(line))
    return "\n".join(lines)


def save(data: str, path: str, style: Style = Style(), size: int = 1024) -> Matrix:
    """Encode data and write it to path. The extension picks the format (.png or .svg)."""
    style = style.validated()
    matrix = build_matrix(data, style.ec)
    target = Path(path)
    suffix = target.suffix.lower()
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".svg":
        target.write_text(to_svg(matrix, style, size), encoding="utf-8")
    elif suffix == ".png":
        to_png(matrix, style, size).save(target, format="PNG")
    else:
        raise ValueError("Output file must end in .png or .svg.")
    return matrix
