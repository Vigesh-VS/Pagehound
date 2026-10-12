import numpy as np

from app import config, embeddings


class Emb:
    def __init__(self, values):
        self.values = values


class Result:
    def __init__(self, n):
        self.embeddings = [Emb([3.0, 4.0] + [0.0] * 6) for _ in range(n)]


class Models:
    def __init__(self, failures):
        self.failures = failures
        self.calls = []

    def embed_content(self, model, contents, config):
        self.calls.append((model, len(contents), config.task_type))
        if self.failures:
            self.failures -= 1
            raise Exception("429 RESOURCE_EXHAUSTED")
        return Result(len(contents))


class Client:
    def __init__(self, failures=0):
        self.models = Models(failures)


def use(monkeypatch, client):
    monkeypatch.setattr(config, "EMBED_BACKEND", "gemini")
    monkeypatch.setattr(embeddings, "_get_client", lambda: client)
    monkeypatch.setattr(embeddings.time, "sleep", lambda s: None)


def test_gemini_backend_batches_and_normalizes(monkeypatch):
    client = Client()
    use(monkeypatch, client)
    vectors = embeddings.embed_documents(["x"] * 120)
    assert vectors.shape == (120, 8)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert [c[1] for c in client.models.calls] == [50, 50, 20]
    assert client.models.calls[0][2] == "RETRIEVAL_DOCUMENT"


def test_gemini_query_uses_query_task(monkeypatch):
    client = Client()
    use(monkeypatch, client)
    vector = embeddings.embed_query("hi")
    assert vector.shape == (8,)
    assert client.models.calls[0][2] == "RETRIEVAL_QUERY"


def test_gemini_backend_retries_when_busy(monkeypatch):
    client = Client(failures=2)
    use(monkeypatch, client)
    assert embeddings.embed_documents(["x"]).shape == (1, 8)
    assert len(client.models.calls) == 3
