import pytest

from qrgen import payloads


def test_url_adds_scheme():
    assert payloads.url("example.com") == "https://example.com"
    assert payloads.url("http://example.com") == "http://example.com"


def test_url_empty():
    with pytest.raises(ValueError):
        payloads.url("   ")


def test_wifi_wpa():
    assert payloads.wifi("Home", "secret") == "WIFI:T:WPA;S:Home;P:secret;;"


def test_wifi_escapes_specials():
    assert payloads.wifi('a;b:c', 'p,w"d') == 'WIFI:T:WPA;S:a\\;b\\:c;P:p\\,w\\"d;;'


def test_wifi_open_and_hidden():
    assert payloads.wifi("Cafe") == "WIFI:T:nopass;S:Cafe;;"
    assert payloads.wifi("Cafe", "pw", hidden=True) == "WIFI:T:WPA;S:Cafe;P:pw;H:true;;"


def test_wifi_needs_ssid():
    with pytest.raises(ValueError):
        payloads.wifi("")


def test_vcard():
    card = payloads.vcard(first="Ada", last="Lovelace", phone="+15551234567", email="ada@example.com")
    lines = card.split("\r\n")
    assert lines[0] == "BEGIN:VCARD" and lines[-1] == "END:VCARD"
    assert "FN:Ada Lovelace" in lines
    assert "TEL;TYPE=CELL:+15551234567" in lines


def test_vcard_needs_name_or_org():
    with pytest.raises(ValueError):
        payloads.vcard(phone="123")


def test_whatsapp():
    assert payloads.whatsapp("+1 (555) 123-4567") == "https://wa.me/15551234567"
    assert payloads.whatsapp("15551234567", "Hi there") == "https://wa.me/15551234567?text=Hi%20there"


def test_whatsapp_short_number():
    with pytest.raises(ValueError):
        payloads.whatsapp("123")


def test_email():
    assert payloads.email("a@b.com") == "mailto:a@b.com"
    assert payloads.email("a@b.com", "Hello", "Line one") == "mailto:a@b.com?subject=Hello&body=Line%20one"
    with pytest.raises(ValueError):
        payloads.email("not-an-address")
