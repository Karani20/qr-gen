import pytest

from qrgen.render import (
    Style,
    build_matrix,
    contrast_ratio,
    contrast_warning,
    normalize_color,
    save,
    to_png,
    to_svg,
    to_terminal,
    version_of,
)


def test_matrix_is_square_and_valid_version():
    m = build_matrix("https://example.com")
    assert all(len(row) == len(m) for row in m)
    assert (len(m) - 17) % 4 == 0
    assert 1 <= version_of(m) <= 40


def test_higher_ec_needs_equal_or_bigger_grid():
    low = build_matrix("https://example.com/some/long/path", "L")
    high = build_matrix("https://example.com/some/long/path", "H")
    assert len(high) >= len(low)


def test_too_much_data():
    with pytest.raises(ValueError):
        build_matrix("x" * 8000, "H")


def test_unicode_encodes():
    assert build_matrix("Habari yako, rafiki. Café ☕")


def test_normalize_color():
    assert normalize_color("#ABC") == "#aabbcc"
    with pytest.raises(ValueError):
        normalize_color("blue")


def test_contrast():
    assert contrast_ratio("#000", "#fff") == pytest.approx(21.0)
    assert contrast_warning(Style(fg="#777777", bg="#888888"))
    assert contrast_warning(Style(fg="#ffffff", bg="#000000"))  # inverted
    assert contrast_warning(Style()) == ""


@pytest.mark.parametrize("shape", ["square", "dots"])
def test_svg(shape):
    svg = to_svg(build_matrix("hello"), Style(shape=shape, fg="#14213d"), 512)
    assert svg.startswith("<svg") and "#14213d" in svg and 'width="512"' in svg


@pytest.mark.parametrize("shape", ["square", "dots"])
def test_png_min_size(shape):
    img = to_png(build_matrix("hello"), Style(shape=shape), 600)
    assert img.width == img.height >= 600


def test_save_by_extension(tmp_path):
    save("hello", str(tmp_path / "a.png"))
    save("hello", str(tmp_path / "sub" / "b.svg"))
    assert (tmp_path / "a.png").stat().st_size > 0
    assert (tmp_path / "sub" / "b.svg").read_text().startswith("<svg")
    with pytest.raises(ValueError):
        save("hello", str(tmp_path / "c.gif"))


def test_terminal_rows():
    m = build_matrix("hello")
    out = to_terminal(m, border=2)
    width = len(m) + 4
    assert all(len(line) == width for line in out.splitlines())


@pytest.mark.parametrize("shape", ["square", "dots"])
@pytest.mark.parametrize("data", ["https://example.com/a?b=c", "Habari yako ☕", "WIFI:T:WPA;S:Home;P:secret;;"])
def test_roundtrip_decode(tmp_path, shape, data):
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "code.png"
    save(data, str(path), Style(shape=shape, ec="Q"), 800)
    img = cv2.imread(str(path))
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert decoded == data
