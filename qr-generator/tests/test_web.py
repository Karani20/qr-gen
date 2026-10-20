import pytest

pytest.importorskip("flask")

from qrgen.web.app import create_app  # noqa: E402


@pytest.fixture
def client():
    return create_app().test_client()


def body(**over):
    data = {"kind": "link", "fields": {"url": "example.com"}, "style": {}, "size": 800}
    data.update(over)
    return data


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Quiet Zone" in res.data
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_generate_link(client):
    res = client.post("/api/generate", json=body())
    assert res.status_code == 200
    d = res.get_json()
    assert d["payload"] == "https://example.com"
    assert d["svg"].startswith("<svg")
    assert d["modules"] == d["version"] * 4 + 17
    assert d["png_px"] >= 800
    assert d["warning"] == ""


def test_generate_wifi(client):
    res = client.post(
        "/api/generate",
        json=body(kind="wifi", fields={"ssid": "Home", "password": "secret", "security": "WPA", "hidden": True}),
    )
    assert res.get_json()["payload"] == "WIFI:T:WPA;S:Home;P:secret;H:true;;"


def test_low_contrast_warning(client):
    res = client.post("/api/generate", json=body(style={"fg": "#777777", "bg": "#888888"}))
    assert res.get_json()["warning"]


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "nope", "fields": {}},
        {"kind": "link", "fields": {"url": ""}},
        {"kind": "whatsapp", "fields": {"phone": "12"}},
        {"style": {"fg": "red"}},
        {"style": {"ec": "Z"}},
        {"style": {"border": "abc"}},
        {"size": 5},
        {"size": 99999},
        {"fields": {"url": "x" * 5000}},
    ],
)
def test_bad_requests(client, payload):
    res = client.post("/api/generate", json=body(**payload))
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_not_json(client):
    assert client.post("/api/generate", data="hello").status_code == 400


def test_too_much_data(client):
    res = client.post("/api/generate", json=body(kind="text", fields={"text": "x" * 3999}, style={"ec": "H"}))
    assert res.status_code == 400


def test_download_png(client):
    res = client.post("/api/download", json=body(format="png"))
    assert res.status_code == 200
    assert res.mimetype == "image/png"
    assert res.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert "attachment" in res.headers["Content-Disposition"]
    assert "qr-link.png" in res.headers["Content-Disposition"]


def test_download_svg(client):
    res = client.post("/api/download", json=body(format="svg", style={"shape": "dots"}))
    assert res.status_code == 200
    assert res.mimetype == "image/svg+xml"
    assert res.data.startswith(b"<svg")


def test_download_bad_format(client):
    assert client.post("/api/download", json=body(format="gif")).status_code == 400


def test_filename_is_sanitized(client):
    res = client.post("/api/download", json=body(kind="link", format="svg"))
    assert 'filename="qr-link.svg"' in res.headers["Content-Disposition"]
