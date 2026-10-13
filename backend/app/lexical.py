import math
import re
from collections import Counter

import numpy as np

STOPWORDS = set(
    "a an and are as at be but by can did do does for from had has have how i if in into is it its me my "
    "of on or our so than that the their them then there these they this those to was we were what when "
    "where which who whom why will with you your about tell show give please explain describe".split()
)

_TOKEN = re.compile(r"[a-z0-9]+(?:[-_./][a-z0-9]+)*")


def _stem(word):
    if word.isdigit() or len(word) <= 3:
        return word
    for suffix in ("ies", "es", "s"):
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def tokenize(text):
    tokens = []
    for match in _TOKEN.findall((text or "").lower()):
        parts = re.split(r"[-_./]", match)
        if len(parts) > 1:
            tokens.append(match)
        tokens.extend(_stem(p) for p in parts if p and p not in STOPWORDS)
    return tokens


class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lengths = np.array([sum(d.values()) for d in self.docs], dtype=np.float32)
        self.avg = float(self.lengths.mean()) if len(self.docs) else 0.0
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query):
        out = np.zeros(len(self.docs), dtype=np.float32)
        if not self.docs or not self.avg:
            return out
        norm = self.k1 * (1 - self.b + self.b * self.lengths / self.avg)
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            tf = np.array([d.get(term, 0) for d in self.docs], dtype=np.float32)
            out += idf * tf * (self.k1 + 1) / (tf + norm)
        return out


def rrf(rankings, k=60):
    fused = {}
    for ranking in rankings:
        for position, index in enumerate(ranking):
            fused[index] = fused.get(index, 0.0) + 1.0 / (k + position + 1)
    return sorted(fused, key=lambda i: (-fused[i], i))
