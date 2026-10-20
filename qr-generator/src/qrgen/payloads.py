

from __future__ import annotations

import re
from urllib.parse import quote

_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.IGNORECASE)


def text(value: str) -> str:
    """Plain text, passed through unchanged.""" 
    if not value:
        raise ValueError("Text is empty.")
    return value

 
def url(value: str) -> str:
    """A web address. Adds https:// when no scheme is given."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Web address is empty.")
    return value if _SCHEME.match(value) else "https://" + value


def _wifi_escape(value: str) -> str:
    return re.sub(r'([\\;,:"])', r"\\\1", value)


def wifi(ssid: str, password: str = "", security: str = "WPA", hidden: bool = False) -> str:
    """Wi-Fi join code understood by iOS and Android cameras.

    security is WPA, WEP or nopass. An empty password means an open network.
    """
    if not (ssid or "").strip():
        raise ValueError("Network name (SSID) is empty.")
    security = security.upper() if security.lower() != "nopass" else "nopass"
    if security not in {"WPA", "WEP", "nopass"}:
        raise ValueError("Security must be WPA, WEP or nopass.")
    if not password:
        security = "nopass"
    out = f"WIFI:T:{security};S:{_wifi_escape(ssid)};"
    if security != "nopass":
        out += f"P:{_wifi_escape(password)};"
    if hidden:
        out += "H:true;"
    return out + ";"


def _vcard_escape(value: str) -> str:
    value = re.sub(r"([\\;,])", r"\\\1", value)
    return re.sub(r"\r?\n", r"\\n", value)


def vcard(
    first: str = "",
    last: str = "",
    org: str = "",
    title: str = "",
    phone: str = "",
    email: str = "",
    website: str = "",
) -> str:
    """Contact card (vCard 3.0)."""
    first, last, org = first.strip(), last.strip(), org.strip()
    if not (first or last or org):
        raise ValueError("Give at least a name or an organization.")
    full_name = f"{first} {last}".strip() or org
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_vcard_escape(last)};{_vcard_escape(first)};;;",
        f"FN:{_vcard_escape(full_name)}",
    ]
    if org:
        lines.append(f"ORG:{_vcard_escape(org)}")
    if title:
        lines.append(f"TITLE:{_vcard_escape(title)}")
    if phone:
        lines.append(f"TEL;TYPE=CELL:{_vcard_escape(phone)}")
    if email:
        lines.append(f"EMAIL:{_vcard_escape(email)}")
    if website:
        lines.append(f"URL:{_vcard_escape(website)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def whatsapp(phone: str, message: str = "") -> str:
    """Link that opens a WhatsApp chat. Phone: country code first, digits only."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 7:
        raise ValueError("Phone number is too short. Use the country code, e.g. 15551234567.")
    link = f"https://wa.me/{digits}"
    message = (message or "").strip()
    if message:
        link += "?text=" + quote(message, safe="")
    return link


KINDS = ("link", "text", "wifi", "contact", "whatsapp", "email")


def build(kind: str, fields: dict) -> str:
    """Build a payload from a kind name and a dict of field values (used by the web app)."""

    def s(key: str) -> str:
        value = fields.get(key, "")
        return "" if value is None else str(value)

    if kind == "link":
        return url(s("url"))
    if kind == "text":
        return text(s("text"))
    if kind == "wifi":
        return wifi(s("ssid"), s("password"), s("security") or "WPA", bool(fields.get("hidden")))
    if kind == "contact":
        return vcard(s("first"), s("last"), s("org"), s("title"), s("phone"), s("email"), s("website"))
    if kind == "whatsapp":
        return whatsapp(s("phone"), s("message"))
    if kind == "email":
        return email(s("to"), s("subject"), s("body"))
    raise ValueError("Unknown kind. Use one of: " + ", ".join(KINDS) + ".")


def email(to: str, subject: str = "", body: str = "") -> str:
    """mailto: link with optional subject and body."""
    to = (to or "").strip()
    if not to or "@" not in to:
        raise ValueError("Enter a valid email address.")
    params = []
    if subject:
        params.append("subject=" + quote(subject, safe=""))
    if body:
        params.append("body=" + quote(body, safe=""))
    return "mailto:" + to + ("?" + "&".join(params) if params else "")
