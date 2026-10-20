"""Command-line interface: qrgen <kind> ... -o out.png"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import payloads
from .render import (
    EC_LEVELS,
    SHAPES,
    Style,
    build_matrix,
    contrast_warning,
    save,
    to_terminal,
    version_of,
)


def _common(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("output")
    g.add_argument("-o", "--output", help="File to write (.png or .svg). Default: qr.png unless --terminal is used alone.")
    g.add_argument("--terminal", action="store_true", help="Also print the code in the terminal.")
    g.add_argument("--light-terminal", action="store_true", help="Terminal has a light background.")
    g.add_argument("--size", type=int, default=1024, help="Minimum width in pixels (default 1024).")

    s = p.add_argument_group("style")
    s.add_argument("--ec", choices=sorted(EC_LEVELS), default="M", help="Error correction level (default M).")
    s.add_argument("--shape", choices=SHAPES, default="square", help="Module shape (default square).")
    s.add_argument("--fg", default="#000000", help="Code color, e.g. #14213d.")
    s.add_argument("--bg", default="#ffffff", help="Background color.")
    s.add_argument("--border", type=int, default=4, help="Quiet zone in modules (default 4).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qrgen",
        description="Generate QR codes for links, text, Wi-Fi, contacts, WhatsApp and email.",
    )
    sub = parser.add_subparsers(dest="kind", required=True, metavar="KIND")

    p = sub.add_parser("link", help="Web address")
    p.add_argument("url")
    _common(p)

    p = sub.add_parser("text", help="Plain text")
    p.add_argument("text")
    _common(p)

    p = sub.add_parser("wifi", help="Wi-Fi network")
    p.add_argument("ssid", help="Network name")
    p.add_argument("--password", default="", help="Leave out for an open network.")
    p.add_argument("--security", default="WPA", choices=["WPA", "WEP", "nopass"])
    p.add_argument("--hidden", action="store_true", help="Network does not broadcast its name.")
    _common(p)

    p = sub.add_parser("contact", help="Contact card (vCard)")
    p.add_argument("--first", default="")
    p.add_argument("--last", default="")
    p.add_argument("--org", default="")
    p.add_argument("--title", default="")
    p.add_argument("--phone", default="")
    p.add_argument("--email", default="")
    p.add_argument("--website", default="")
    _common(p)

    p = sub.add_parser("whatsapp", help="Open a WhatsApp chat")
    p.add_argument("phone", help="Country code first, digits only, e.g. 15551234567")
    p.add_argument("--message", default="", help="Pre-filled message.")
    _common(p)

    p = sub.add_parser("email", help="Compose an email")
    p.add_argument("to")
    p.add_argument("--subject", default="")
    p.add_argument("--body", default="")
    _common(p)

    return parser


def payload_from_args(args: argparse.Namespace) -> str:
    kind = args.kind
    if kind == "link":
        return payloads.url(args.url)
    if kind == "text":
        return payloads.text(args.text)
    if kind == "wifi":
        return payloads.wifi(args.ssid, args.password, args.security, args.hidden)
    if kind == "contact":
        return payloads.vcard(args.first, args.last, args.org, args.title, args.phone, args.email, args.website)
    if kind == "whatsapp":
        return payloads.whatsapp(args.phone, args.message)
    if kind == "email":
        return payloads.email(args.to, args.subject, args.body)
    raise ValueError(f"Unknown kind: {kind}")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = payload_from_args(args)
        style = Style(args.fg, args.bg, args.shape, args.border, args.ec).validated()
        warning = contrast_warning(style)
        if warning:
            print("Warning: " + warning, file=sys.stderr)

        output = args.output
        if output is None and not args.terminal:
            output = "qr.png"

        matrix = build_matrix(data, style.ec)
        if args.terminal:
            print(to_terminal(matrix, light_terminal=args.light_terminal))
        if output:
            save(data, output, style, args.size)
            print(f"Saved {output} (version {version_of(matrix)}, {len(matrix)}x{len(matrix)} modules)")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
