import time

import numpy as np

from . import config

_model = None
_client = None
BATCH = 50


def _normalize(vectors):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def _use_gemini():
    return config.EMBED_BACKEND == "gemini"


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=config.EMBED_MODEL)
    return _model


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _gemini_embed(texts, task):
    from google.genai import types

    out = []
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        for attempt in range(5):
            try:
                result = _get_client().models.embed_content(
                    model=config.GEMINI_EMBED_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task, output_dimensionality=config.GEMINI_EMBED_DIMS),
                )
                out.extend(e.values for e in result.embeddings)
                break
            except Exception as exc:
                text = str(exc)
                busy = "429" in text or "RESOURCE_EXHAUSTED" in text or "503" in text
                if not busy or attempt == 4:
                    raise
                time.sleep(2 ** (attempt + 1))
    return _normalize(np.array(out, dtype=np.float32))


def warmup():
    if not _use_gemini():
        _get_model()


def embed_documents(texts):
    if _use_gemini():
        return _gemini_embed(texts, "RETRIEVAL_DOCUMENT")
    vectors = np.array(list(_get_model().embed(texts, batch_size=32)), dtype=np.float32)
    return _normalize(vectors)


def embed_query(text):
    if _use_gemini():
        return _gemini_embed([text], "RETRIEVAL_QUERY")[0]
    vectors = np.array(list(_get_model().query_embed([text])), dtype=np.float32)
    return _normalize(vectors)[0]
