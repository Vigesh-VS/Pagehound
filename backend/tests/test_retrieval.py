import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import config, llm
from app.main import app
from app.retrieval import is_broad, pick_chunks
from tests.test_api import patched, text_pdf, upload  # noqa: F401


@pytest.mark.parametrize(
    "question",
    ["What is this document about?", "Summarize the file", "give me an overview", "main points please", "explain this lecture", "tell me about this"],
)
def test_broad_questions_are_detected(question):
    assert is_broad(question)


@pytest.mark.parametrize("question", ["What is the penalty fee?", "solve question 2", "what does step 3 compute"])
def test_specific_questions_are_not_broad(question):
    assert not is_broad(question)


def test_small_documents_are_sent_whole_and_in_order():
    assert pick_chunks(np.array([0.1, 0.9, 0.3]), "anything") == [0, 1, 2]


def test_specific_questions_get_the_best_chunks_in_reading_order():
    scores = np.zeros(50)
    scores[[40, 7, 22]] = [0.9, 0.8, 0.7]
    picked = pick_chunks(scores, "what is the penalty fee")
    assert len(picked) == config.TOP_K and {7, 22, 40} <= set(picked) and picked == sorted(picked)


def test_broad_questions_spread_across_the_whole_document():
    scores = np.zeros(200)
    scores[[150, 151, 152]] = 1.0
    picked = pick_chunks(scores, "what is this document about")
    assert len(picked) == config.BROAD_TOP_K and len(set(picked)) == len(picked) and picked == sorted(picked)
    assert {150, 151, 152} <= set(picked)
    assert min(picked) < 20 and max(picked) > 180 and any(80 < i < 120 for i in picked)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def long_pdf(pages=24):
    doc = pymupdf.open()
    for number in range(pages):
        doc.new_page().insert_text((72, 100), f"Section {number + 1} discusses topic number {number + 1} with enough words to be indexed properly.")
    data = doc.tobytes()
    doc.close()
    return data


def test_a_broad_question_reaches_the_model_with_chunks_from_the_whole_file(client, monkeypatch):
    seen = {}

    def spy(question, sources, history):
        seen["pages"] = [s["page"] for s in sources]
        return "ok"

    monkeypatch.setattr(llm, "answer", spy)
    doc_id = upload(client, long_pdf(), user="reader").json()["doc_id"]
    client.post("/ask", json={"doc_id": doc_id, "question": "What is this document about?"}, headers={"x-debug-user": "reader"})
    assert len(seen["pages"]) == config.BROAD_TOP_K
    assert min(seen["pages"]) <= 3 and max(seen["pages"]) >= 22 and any(9 <= p <= 15 for p in seen["pages"])

    client.post("/ask", json={"doc_id": doc_id, "question": "what is discussed in section 12"}, headers={"x-debug-user": "reader"})
    assert len(seen["pages"]) == config.TOP_K


def test_question_can_span_earlier_files_in_the_same_chat(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(llm, "answer", lambda q, sources, history: seen.setdefault("labels", [s["label"] for s in sources]) and "ok")
    first = upload(client, long_pdf(), user="multi").json()["doc_id"]
    second = upload(client, text_pdf(), user="multi").json()["doc_id"]
    r = client.post("/ask", json={"doc_ids": [first, second], "question": "what is this about"}, headers={"x-debug-user": "multi"})
    assert r.status_code == 200
    assert len(seen["labels"]) > 0 and all(" - " in label for label in seen["labels"])
