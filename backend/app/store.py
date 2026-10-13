import threading
import time
import uuid
from dataclasses import dataclass, field

from . import config


@dataclass
class Document:
    doc_id: str
    owner: str
    filename: str
    chunks: list
    vectors: object
    created: float = field(default_factory=time.time)
    lexical: object = None


class DocStore:
    def __init__(self, ttl, max_docs):
        self.ttl = ttl
        self.max_docs = max_docs
        self.docs = {}
        self.lock = threading.Lock()

    def _evict(self):
        now = time.time()
        for doc_id in [d for d, doc in self.docs.items() if now - doc.created > self.ttl]:
            del self.docs[doc_id]
        while len(self.docs) > self.max_docs:
            oldest = min(self.docs.values(), key=lambda doc: doc.created)
            del self.docs[oldest.doc_id]

    def add(self, owner, filename, chunks, vectors):
        doc = Document(uuid.uuid4().hex[:16], owner, filename, chunks, vectors)
        with self.lock:
            self.docs[doc.doc_id] = doc
            self._evict()
        return doc

    def get(self, doc_id, owners):
        with self.lock:
            self._evict()
            doc = self.docs.get(doc_id)
        if doc is None or doc.owner not in owners:
            return None
        return doc


store = DocStore(config.DOC_TTL_SECONDS, config.MAX_DOCS)
