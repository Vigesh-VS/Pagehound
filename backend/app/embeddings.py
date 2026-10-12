import numpy as np

from . import config

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=config.EMBED_MODEL)
    return _model


def _normalize(vectors):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def warmup():
    _get_model()


def embed_documents(texts):
    vectors = np.array(list(_get_model().embed(texts, batch_size=32)), dtype=np.float32)
    return _normalize(vectors)


def embed_query(text):
    vectors = np.array(list(_get_model().query_embed([text])), dtype=np.float32)
    return _normalize(vectors)[0]
