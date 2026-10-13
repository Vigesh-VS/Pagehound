import numpy as np
import pymupdf
import pytest
import shutil
from PIL import Image, ImageDraw, ImageFont

from app import pdf_utils
from app.pdf_utils import _good, _long_runs, _without_lines

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")


def test_long_runs_marks_only_long_lines():
    mask = np.zeros((3, 12), bool)
    mask[0, 2:10] = True
    mask[1, 0:3] = True
    runs = _long_runs(mask, 5)
    assert runs[0, 2:10].all() and not runs[0, :2].any() and not runs[1].any()


def grid(columns=4, rows=5):
    img = Image.new("L", (1200, 900), 255)
    d = ImageDraw.Draw(img)
    for i in range(rows + 1):
        d.line((150, 200 + i * 100, 1050, 200 + i * 100), fill=0, width=3)
    for j in range(columns + 1):
        d.line((150 + j * 225, 200, 150 + j * 225, 200 + rows * 100), fill=0, width=3)
    return img


def test_grid_lines_are_removed_but_plain_rules_are_not():
    assert _without_lines(grid()) is not None
    ruled = Image.new("L", (1200, 900), 255)
    d = ImageDraw.Draw(ruled)
    for y in range(100, 900, 60):
        d.line((50, y, 1150, y), fill=0, width=2)
    assert _without_lines(ruled) is None


def test_good_accepts_short_but_very_clean_text():
    assert _good(("HXP-250", 40, 94))
    assert not _good(("noise", 25, 29))
    assert _good(("long text", 300, 70))


def text_image(lines, angle=0):
    img = Image.new("RGB", (1400, 900), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    for i, line in enumerate(lines):
        d.text((80, 80 + i * 70), line, font=f, fill="black")
    return img.rotate(angle, expand=True, fillcolor="white")


@needs_tesseract
def test_sideways_page_is_rotated_before_reading():
    lines = ["Warranty valid until 8 August 2031", "Registration number GLW 771204", "Keep this page with the site records", "Serial number checked by the engineer"]
    text = pdf_utils.ocr_image(text_image(lines, 90))
    assert "2031" in text and "771204" in text


@needs_tesseract
def test_photo_on_a_text_page_is_read(tmp_path):
    photo = text_image(["Model INV-HX-250", "Serial HXP-250-7731-K", "Rated output 250 kW"])
    path = tmp_path / "p.png"
    photo.save(path)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This page has normal text describing the inverter installed at the site. " * 2, fontsize=9)
    page.insert_image(pymupdf.Rect(72, 120, 520, 410), filename=str(path))
    pages, _ = pdf_utils.extract_pages(doc.tobytes())
    assert "[Text in image]" in pages[0].text and "7731" in pages[0].text and not pages[0].ocr
