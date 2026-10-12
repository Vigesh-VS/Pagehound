import pytest

from app import config, llm


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, behaviors):
        self.behaviors = behaviors
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        result = self.behaviors[model]
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


class FakeClient:
    def __init__(self, behaviors):
        self.models = FakeModels(behaviors)


SOURCES = [{"page": 1, "text": "hello"}]


def setup(monkeypatch, models, behaviors):
    client = FakeClient(behaviors)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(config, "GEMINI_MODELS", models)
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    return client


def test_falls_back_when_first_model_is_rate_limited(monkeypatch):
    client = setup(monkeypatch, ["a", "b"], {"a": Exception("429 RESOURCE_EXHAUSTED"), "b": "from b"})
    assert llm.answer("q", SOURCES, []) == "from b"
    assert client.models.calls == ["a", "b"]


def test_skips_unknown_models(monkeypatch):
    setup(monkeypatch, ["a", "b"], {"a": Exception("404 NOT_FOUND"), "b": "from b"})
    assert llm.answer("q", SOURCES, []) == "from b"


def test_all_rate_limited_reports_rate_limit(monkeypatch):
    setup(monkeypatch, ["a", "b"], {"a": Exception("429"), "b": Exception("429")})
    with pytest.raises(llm.LLMError) as info:
        llm.answer("q", SOURCES, [])
    assert info.value.rate_limited is True


def test_other_errors_fall_back_to_next_model(monkeypatch):
    client = setup(monkeypatch, ["a", "b"], {"a": Exception("503 UNAVAILABLE"), "b": "from b"})
    assert llm.answer("q", SOURCES, []) == "from b"
    assert client.models.calls == ["a", "b"]


def test_all_models_failing_reports_failure(monkeypatch):
    setup(monkeypatch, ["a", "b"], {"a": Exception("500 x"), "b": Exception("500 y")})
    with pytest.raises(llm.LLMError) as info:
        llm.answer("q", SOURCES, [])
    assert info.value.rate_limited is False


def test_gemma_gets_the_system_prompt_inside_the_contents(monkeypatch):
    seen = {}

    class Models:
        def generate_content(self, model, contents, config):
            seen["contents"] = contents
            seen["system"] = config.system_instruction
            return FakeResponse("ok")

    client = type("C", (), {"models": Models()})()
    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(config, "GEMINI_MODELS", ["gemma-4-31b-it"])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    llm.answer("q", SOURCES, [])
    assert seen["system"] is None and "using only the excerpts" in seen["contents"]
