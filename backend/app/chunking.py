from dataclasses import dataclass


@dataclass
class Chunk:
    page: int
    text: str
    ocr: bool
    label: str = ""


def chunk_pages(pages, size, overlap):
    chunks = []
    for page in pages:
        text = " ".join(page.text.split())
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                half = start + size // 2
                cut = text.rfind(". ", half, end)
                cut = cut + 1 if cut != -1 else text.rfind(" ", half, end)
                if cut > start:
                    end = cut
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(page.number, piece, page.ocr, page.label))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
