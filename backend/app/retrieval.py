import re

import numpy as np

from . import config
from .lexical import BM25, rrf
from .rerank import rerank as rerank_texts

BROAD = re.compile(
    r"\b(summar\w*|overview|outline|gist|everything|what(?:'?s| is| are)? (?:this|it|these|the \w+) about|"
    r"main (?:points?|topics?|ideas?)|key (?:points?|takeaways?|ideas?|concepts?)|"
    r"explain (?:this|the) (?:document|file|pdf|paper|doc|chapter|lecture|notes?)|"
    r"what is (?:this|the) (?:document|file|pdf|doc|paper)|describe (?:this|the)|tell me (?:about|everything))\b",
    re.IGNORECASE,
)


def is_broad(question):
    return bool(BROAD.search(question))


def _setting(value, default):
    return default if value is None else value


def lexical_index(doc):
    index = getattr(doc, "lexical", None)
    if index is None:
        index = BM25([c.text for c in doc.chunks])
        doc.lexical = index
    return index


_CODE = re.compile(r"\b(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9]+(?:-[a-z0-9]+)*\b", re.I)


def identifiers(query):
    return {m.group(0).lower() for m in _CODE.finditer(query or "")}


def boost_exact(doc, order, query):
    codes = identifiers(query)
    if not codes:
        return order
    patterns = [re.compile(rf"(?<![a-z0-9-]){re.escape(c)}(?![a-z0-9]|-[a-z0-9])", re.I) for c in codes]
    hits = [i for i in order if any(p.search(doc.chunks[i].text) for p in patterns)]
    if not hits or len(hits) > max(3, len(order) // 4):
        return order
    return hits + [i for i in order if i not in set(hits)]


def rank(doc, query_vector, query, hybrid=None):
    dense = doc.vectors @ query_vector
    order = [int(i) for i in np.argsort(-dense, kind="stable")]
    if _setting(hybrid, config.HYBRID):
        lex = lexical_index(doc).scores(query)
        lex_order = [int(i) for i in np.argsort(-lex, kind="stable") if lex[i] > 0]
        if lex_order:
            order = rrf([order, lex_order])
        order = boost_exact(doc, order, query)
    return order, dense


def rerank_order(doc, order, query, candidates=None):
    head = order[: _setting(candidates, config.RERANK_CANDIDATES)]
    scores = rerank_texts(query, [doc.chunks[i].text for i in head])
    if scores is None:
        return order
    ranked = [i for _, i in sorted(zip(scores, head), key=lambda pair: -pair[0])]
    return ranked + order[len(head):]


def diversify(order, vectors, k, lam=None):
    lam = _setting(lam, config.MMR_LAMBDA)
    pool = order[: max(k * 3, k)]
    if vectors is None or len(pool) <= k:
        return pool[:k]
    relevance = {i: 1.0 - p / len(pool) for p, i in enumerate(pool)}
    chosen = []
    remaining = list(pool)
    while remaining and len(chosen) < k:
        def gain(i):
            overlap = max(max(float(vectors[i] @ vectors[j]), 0.0) for j in chosen) if chosen else 0.0
            return lam * relevance[i] - (1 - lam) * overlap
        best = max(remaining, key=gain)
        chosen.append(best)
        remaining.remove(best)
    return chosen


def choose(order, total, broad, limit, vectors=None, mmr=False):
    if total <= limit:
        return list(range(total))
    if not broad:
        return diversify(order, vectors, limit) if mmr else order[:limit]
    half = limit // 2
    chosen = diversify(order, vectors, half) if mmr else order[:half]
    for index in np.linspace(0, total - 1, num=limit - len(chosen), dtype=int):
        if int(index) not in chosen:
            chosen.append(int(index))
    for index in order:
        if len(chosen) >= limit:
            break
        if index not in chosen:
            chosen.append(index)
    return chosen


def pick_chunks(scores, question, limit=None):
    broad = is_broad(question)
    if limit is None:
        limit = config.BROAD_TOP_K if broad else config.TOP_K
    order = [int(i) for i in np.argsort(-np.asarray(scores), kind="stable")]
    return sorted(choose(order, len(scores), broad, limit))


def select(doc, query_vector, query, question, limit, hybrid=None, mmr=None, rerank=None):
    order, dense = rank(doc, query_vector, query, hybrid)
    if _setting(rerank, config.RERANK) and len(order) > limit:
        order = rerank_order(doc, order, query)
        if _setting(hybrid, config.HYBRID):
            order = boost_exact(doc, order, query)
    picked = choose(order, len(order), is_broad(question), limit, doc.vectors, _setting(mmr, config.MMR))
    return picked, dense


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


def gather_sources(docs, query_vector, question, query=None):
    multi = len(docs) > 1
    limit = config.BROAD_TOP_K if is_broad(question) else config.TOP_K
    share = max(limit // len(docs), 4) if multi else limit
    out = []
    for doc in docs:
        picked, scores = select(doc, query_vector, query or question, question, share)
        for i in sorted(picked):
            chunk = doc.chunks[i]
            label = chunk.label or f"Page {chunk.page}"
            out.append({
                "page": chunk.page,
                "label": f"{doc.filename} - {label}" if multi else chunk.label,
                "text": chunk.text,
                "score": float(scores[i]),
            })
    return out
