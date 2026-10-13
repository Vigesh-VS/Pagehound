import logging

from . import config

log = logging.getLogger("uvicorn.error")

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _model = TextCrossEncoder(model_name=config.RERANK_MODEL)
    return _model


def warmup():
    if config.RERANK:
        _get_model()


def rerank(query, texts):
    try:
        return [float(s) for s in _get_model().rerank(query, texts, batch_size=16)]
    except Exception as exc:
        log.error("Reranking failed, keeping the first-stage order: %s", exc)
        return None
