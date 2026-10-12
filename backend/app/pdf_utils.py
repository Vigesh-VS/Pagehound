from dataclasses import dataclass

import pymupdf
import pytesseract
from PIL import Image

from . import config

if config.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


class ExtractError(Exception):
    pass


PdfError = ExtractError


@dataclass
class PageText:
    number: int
    text: str
    ocr: bool = False
    label: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = f"Page {self.number}"


def ocr_image(image):
    try:
        return pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractError("The OCR engine (Tesseract) is not installed on the server.") from exc


def _ocr_page(page):
    pix = page.get_pixmap(dpi=config.OCR_DPI, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return ocr_image(image)


def extract_pages(data, max_pages=None):
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ExtractError("Could not read this file as a PDF.") from exc

    if doc.needs_pass:
        doc.close()
        raise ExtractError("Password-protected PDFs are not supported.")

    total = doc.page_count
    pages = []
    for index in range(min(total, max_pages or config.MAX_PAGES)):
        page = doc[index]
        text = page.get_text("text").strip()
        used_ocr = False
        if len(text) < config.OCR_MIN_CHARS:
            ocr_text = _ocr_page(page)
            if len(ocr_text) > len(text):
                text, used_ocr = ocr_text, True
        pages.append(PageText(index + 1, text, used_ocr))
    doc.close()
    return pages, total
