import re
from dataclasses import dataclass

import numpy as np
import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps

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


def _read(image, options=""):
    data = pytesseract.image_to_data(image, config=options, output_type=pytesseract.Output.DICT)
    lines, current, key, score, confs = [], [], None, 0, []
    for i, word in enumerate(data["text"]):
        word = word.strip()
        conf = float(data["conf"][i])
        if not word or conf < 0:
            continue
        line = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key is not None and line != key:
            lines.append(" ".join(current))
            current = []
        key = line
        current.append(word)
        confs.append(conf)
        if conf >= 60:
            score += len(word)
    if current:
        lines.append(" ".join(current))
    mean = sum(confs) / len(confs) if confs else 0.0
    return "\n".join(lines).strip(), score, mean


def _rotation(image):
    try:
        osd = pytesseract.image_to_osd(image, config="--psm 0 -c min_characters_to_try=5")
    except pytesseract.TesseractError:
        return 0
    match = re.search(r"Rotate: (\d+)", osd)
    confidence = re.search(r"Orientation confidence: ([\d.]+)", osd)
    if not match or not confidence or float(confidence.group(1)) < 1.5:
        return 0
    return int(match.group(1)) % 360


def _long_runs(mask, length):
    height, width = mask.shape
    if width < length:
        return np.zeros_like(mask, dtype=bool)
    sums = np.zeros((height, width + 1), dtype=np.int32)
    np.cumsum(mask, axis=1, out=sums[:, 1:])
    full = (sums[:, length:] - sums[:, : width - length + 1]) == length
    delta = np.zeros((height, width + 1), dtype=np.int32)
    delta[:, : width - length + 1] += full
    delta[:, length:] -= full
    return np.cumsum(delta, axis=1)[:, :width] > 0


def _groups(flags):
    edges = np.diff(np.concatenate(([0], flags.astype(np.int8), [0])))
    return int((edges == 1).sum())


def _without_lines(gray):
    dark = np.asarray(gray) < 140
    margin_y, margin_x = dark.shape[0] // 25, dark.shape[1] // 25
    dark[:margin_y, :] = dark[-margin_y:, :] = False
    dark[:, :margin_x] = dark[:, -margin_x:] = False
    length = max(60, min(dark.shape) // 12)
    across = _long_runs(dark, length)
    down = _long_runs(dark.T, length).T
    if _groups(across.any(axis=1)) < 3 or _groups(down.any(axis=0)) < 3:
        return None
    clean = np.asarray(gray).copy()
    clean[across | down] = 255
    return Image.fromarray(clean)


def _good(result):
    _, score, mean = result
    return mean >= config.OCR_GOOD_CONF and (score >= config.OCR_GOOD_CHARS or mean >= 85 and score >= 20)


def ocr_best(image):
    try:
        gray = ImageOps.autocontrast(ImageOps.grayscale(image))
        best = _read(gray)
        unlined = _without_lines(gray)
        if unlined is not None:
            best = max([best, _read(unlined, "--psm 4")], key=lambda c: c[1])
        if _good(best):
            return best
        angle = _rotation(gray)
        if angle:
            gray = gray.rotate(-angle, expand=True, fillcolor=255)
            turned = _read(gray)
            if _good(turned):
                return turned
            best = max([best, turned], key=lambda c: c[1])
        return max([best, _read(gray.filter(ImageFilter.MedianFilter(5)))], key=lambda c: c[1])
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractError("The OCR engine (Tesseract) is not installed on the server.") from exc


def ocr_image(image):
    return ocr_best(image)[0]


def _render(page, dpi, clip=None):
    pix = page.get_pixmap(dpi=dpi, alpha=False, clip=clip)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _ocr_page(page):
    return ocr_image(_render(page, config.OCR_DPI))


def _image_text(page):
    if not config.OCR_IMAGES:
        return ""
    area = abs(page.rect)
    texts = []
    for xref, *_ in page.get_images(full=True)[:6]:
        for rect in page.get_image_rects(xref)[:1]:
            rect = rect & page.rect
            if rect.is_empty or abs(rect) < area * config.OCR_IMAGE_MIN_AREA or min(rect.width, rect.height) < 100:
                continue
            text, score, _ = ocr_best(_render(page, int(config.OCR_DPI * 1.5), rect))
            if score >= 20:
                texts.append(text)
        if len(texts) >= 3:
            break
    return "\n\n".join(f"[Text in image]\n{t}" for t in texts)


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
        else:
            extra = _image_text(page)
            if extra:
                text = f"{text}\n\n{extra}"
        pages.append(PageText(index + 1, text, used_ocr))
    doc.close()
    return pages, total
