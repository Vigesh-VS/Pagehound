import re
from dataclasses import dataclass


@dataclass
class Chunk:
    page: int
    text: str
    ocr: bool
    label: str = ""


_TABLE = re.compile(r"^(summary|rows \d|.* rows \d)", re.I)
_NUMBERED = re.compile(r"^(\d+(\.\d+)*[.)]?|[ivxlc]+\.|chapter \d+|section \d+|part \d+)\s+\S", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(\[]?[A-Z0-9])")
_END = (".", "!", "?", ":", ";", ",")


def _is_heading(line, previous, following):
    text = line.strip()
    if not text or len(text) > 80 or len(text.split()) > 12:
        return False
    if text.startswith("#"):
        return True
    if previous and not previous.rstrip().endswith((".", "!", "?", ":")):
        return False
    if text.endswith(_END) or (following and following[:1].islower()):
        return False
    if _NUMBERED.match(text) or text.isupper():
        return True
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", text)]
    if not words or not text[0].isupper():
        return False
    long = [w for w in words if len(w) > 3]
    return len(words) <= 4 or sum(w[0].isupper() for w in long) * 2 >= len(long)


def _sections(text, heading):
    lines = [l.strip() for l in text.splitlines()]
    sections, body, previous = [], [], ""
    for n, line in enumerate(lines):
        if not line:
            previous = "."
            continue
        following = next((l for l in lines[n + 1:] if l), "")
        if _is_heading(line, previous, following):
            if body:
                sections.append((heading, " ".join(body)))
                body = []
            heading = line.lstrip("#").strip()
        else:
            body.append(line)
        previous = line
    if body:
        sections.append((heading, " ".join(body)))
    return sections, heading


def _sentences(text, size):
    out = []
    for sentence in _SENTENCE.split(" ".join(text.split())):
        while len(sentence) > size:
            cut = sentence.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            out.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            out.append(sentence)
    return out


def _pack(pieces, size, overlap, joiner=" "):
    chunks, current, length = [], [], 0
    for piece in pieces:
        if current and length + len(piece) + 1 > size:
            chunks.append(joiner.join(current))
            carry, carried = [], 0
            for prev in reversed(current):
                if carried + len(prev) > overlap:
                    break
                carry.insert(0, prev)
                carried += len(prev) + 1
            current, length = carry, carried
        current.append(piece)
        length += len(piece) + 1
    if current:
        chunks.append(joiner.join(current))
    return chunks


def chunk_fixed(pages, size, overlap):
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


def _merge_small(texts, size):
    out = []
    for text in texts:
        if out and (len(out[-1]) < size // 3 or len(text) < size // 3) and len(out[-1]) + len(text) + 1 <= size:
            out[-1] = f"{out[-1]}\n{text}"
        else:
            out.append(text)
    return out


def chunk_structured(pages, size, overlap):
    chunks, heading = [], ""
    for page in pages:
        if _TABLE.match(page.label or ""):
            for text in _pack([l.strip() for l in page.text.splitlines() if l.strip()], size, 0, "\n"):
                chunks.append(Chunk(page.number, text, page.ocr, page.label))
            continue
        sections, heading = _sections(page.text, heading)
        texts = []
        for title, body in sections:
            room = size - len(title) - 1 if title else size
            for text in _pack(_sentences(body, room), room, overlap):
                texts.append(f"{title}\n{text}" if title else text)
        for text in _merge_small(texts, size):
            chunks.append(Chunk(page.number, text, page.ocr, page.label))
    return chunks


def chunk_pages(pages, size, overlap, structured=None):
    from . import config

    use = config.STRUCTURED_CHUNKS if structured is None else structured
    return (chunk_structured if use else chunk_fixed)(pages, size, overlap)
