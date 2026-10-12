import re

import numpy as np

from . import config

BROAD = re.compile(
    r"\b(summar\w*|overview|outline|gist|about|everything|"
    r"main (?:points?|topics?|ideas?)|key (?:points?|takeaways?|ideas?|concepts?)|"
    r"explain (?:this|the) (?:document|file|pdf|paper|doc|chapter|lecture|notes?)|"
    r"what is (?:this|the) (?:document|file|pdf|doc|paper)|describe (?:this|the)|tell me (?:about|everything))\b",
    re.IGNORECASE,
)


def is_broad(question):
    return bool(BROAD.search(question))


def pick_chunks(scores, question, limit=None):
    total = len(scores)
    if limit is None:
        limit = config.BROAD_TOP_K if is_broad(question) else config.TOP_K
    if total <= limit:
        return list(range(total))

    ranked = [int(i) for i in np.argsort(scores)[::-1]]
    if not is_broad(question):
        return sorted(ranked[:limit])

    best = ranked[: limit // 2]
    chosen = list(best)
    for index in np.linspace(0, total - 1, num=limit - len(best), dtype=int):
        if int(index) not in chosen:
            chosen.append(int(index))
    for index in ranked:
        if len(chosen) >= limit:
            break
        if index not in chosen:
            chosen.append(index)
    return sorted(chosen)


KINDS = {
    "pdf": (".pdf",),
    "csv": (".csv", ".tsv"),
    "excel": (".xlsx", ".xls"),
    "spreadsheet": (".xlsx", ".xls", ".csv", ".tsv"),
    "xlsx": (".xlsx",),
    "word": (".docx",),
    "docx": (".docx",),
    "ppt": (".pptx",),
    "powerpoint": (".pptx",),
    "slides": (".pptx",),
    "image": (".png", ".jpg", ".jpeg", ".webp"),
}


def narrow_docs(docs, question):
    if len(docs) < 2:
        return docs
    q = question.lower()
    named = [d for d in docs if d.filename.lower().rsplit(".", 1)[0] in q or d.filename.lower() in q]
    if named:
        return named
    exts = set()
    for word, group in KINDS.items():
        if re.search(rf"\b{word}\b", q):
            exts.update(group)
    if exts:
        typed = [d for d in docs if d.filename.lower().endswith(tuple(exts))]
        if typed:
            return typed
    return docs


def gather_sources(docs, query_vector, question):
    multi = len(docs) > 1
    limit = config.BROAD_TOP_K if is_broad(question) else config.TOP_K
    share = max(limit // len(docs), 4) if multi else limit
    out = []
    for doc in docs:
        scores = doc.vectors @ query_vector
        total = len(scores)
        top = pick_chunks(scores, question, share)
        for i in top:
            chunk = doc.chunks[i]
            label = chunk.label or f"Page {chunk.page}"
            out.append({
                "page": chunk.page,
                "label": f"{doc.filename} - {label}" if multi else chunk.label,
                "text": chunk.text,
                "score": float(scores[i]),
            })
    return out
