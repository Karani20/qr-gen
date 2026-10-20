"""qrgen: a small QR code generator."""

from . import payloads
from .render import Style, build_matrix, contrast_ratio, save, to_png, to_svg, to_terminal

__all__ = ["payloads", "Style", "build_matrix", "contrast_ratio", "save", "to_png", "to_svg", "to_terminal"]
__version__ = "1.0.0"
