import sys
from pathlib import Path

import numpy as np
import pytest

from app import retrieval
from app.chunking import Chunk, chunk_fixed, chunk_structured
from app.lexical import BM25, rrf, tokenize
from app.pdf_utils import PageText
from app.query import contextualize, is_follow_up
from app.store import Document


def make_doc(texts, vectors):
    chunks = [Chunk(i + 1, t, False) for i, t in enumerate(texts)]
    return Document("d", "u", "f.pdf", chunks, np.asarray(vectors, dtype=np.float32))


def unit(i, n=4):
    v = np.zeros(n, dtype=np.float32)
    v[i] = 1.0
    return v


def test_tokenize_keeps_codes_and_their_parts():
    tokens = tokenize("Use filter AX2-HEPA-13 and form HR-17B.")
    assert "ax2-hepa-13" in tokens and "hepa" in tokens and "hr-17b" in tokens
    assert "and" not in tokens


def test_tokenize_folds_simple_plurals():
    assert tokenize("filters policies") == ["filter", "policy"]


def test_bm25_prefers_the_chunk_with_the_rare_term():
    index = BM25(["error codes for the purifier", "error E4 is a wifi failure", "error codes and more error codes"])
    scores = index.scores("what is E4")
    assert int(np.argmax(scores)) == 1


def test_rrf_rewards_agreement_between_rankings():
    assert rrf([[0, 1, 2], [2, 1, 0], [1, 2, 0]])[0] == 1


def test_hybrid_finds_an_exact_code_dense_search_misses():
    texts = ["general warranty information", "order ORD-1047 was returned", "shipping times", "contact details"]
    doc = make_doc(texts, [unit(0), unit(1), unit(2), unit(3)])
    query_vector = unit(0)
    dense_only, _ = retrieval.select(doc, query_vector, "status of ORD-1047", "status of ORD-1047", 1, hybrid=False, mmr=False, rerank=False)
    hybrid, _ = retrieval.select(doc, query_vector, "status of ORD-1047", "status of ORD-1047", 2, hybrid=True, mmr=False, rerank=False)
    assert dense_only == [0]
    assert 1 in hybrid


def test_mmr_skips_near_duplicates():
    dup = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    vectors = np.stack([dup, dup, dup, np.array([0.7, 0.7, 0, 0], dtype=np.float32) / np.sqrt(0.98), unit(2)])
    order = [0, 1, 2, 3, 4]
    plain = order[:2]
    diverse = retrieval.diversify(order, vectors, 2, lam=0.6)
    assert plain == [0, 1]
    assert diverse[0] == 0 and diverse[1] not in (1, 2)


def test_rerank_reorders_candidates(monkeypatch):
    doc = make_doc(["a", "b", "c", "d"], [unit(0)] * 4)
    monkeypatch.setattr(retrieval, "rerank_texts", lambda q, texts: [0.1, 0.2, 0.9, 0.3])
    assert retrieval.rerank_order(doc, [0, 1, 2, 3], "q", candidates=4) == [2, 3, 1, 0]


def test_rerank_failure_keeps_first_stage_order(monkeypatch):
    doc = make_doc(["a", "b", "c"], [unit(0)] * 3)
    monkeypatch.setattr(retrieval, "rerank_texts", lambda q, texts: None)
    assert retrieval.rerank_order(doc, [2, 0, 1], "q") == [2, 0, 1]


@pytest.mark.parametrize("question", ["And for the secondary one?", "What about international trips?", "Why?", "Where is it located?", "Who holds that review?"])
def test_follow_ups_are_detected(question):
    assert is_follow_up(question)


@pytest.mark.parametrize("question", ["What is the refund policy for damaged items?", "Summarize chapter 3", "How many images are in the dataset?"])
def test_standalone_questions_are_not_rewritten(question):
    assert not is_follow_up(question)


def test_contextualize_adds_the_previous_question():
    history = [{"role": "user", "text": "What does error E2 mean?"}, {"role": "assistant", "text": "A fan fault."}]
    assert contextualize("What should I do about it?", history) == "What does error E2 mean? What should I do about it?"
    assert contextualize("What does E5 mean?", history) == "What does E5 mean?"
    assert contextualize("And this?", []) == "And this?"


@pytest.mark.parametrize("question", ["What should I do about it?", "What about the warranty?"])
def test_about_alone_does_not_make_a_question_broad(question):
    assert not retrieval.is_broad(question)


def test_structured_chunks_keep_their_heading():
    text = "1. Refund Policy\nRefunds are possible within 30 days of purchase.\n\n2. Shipping\nOrders ship in two business days."
    chunks = chunk_structured([PageText(1, text)], 900, 150)
    joined = "\n".join(c.text for c in chunks)
    assert "1. Refund Policy\nRefunds are possible" in joined and "2. Shipping\nOrders ship" in joined


def test_wrapped_pdf_lines_are_not_headings():
    text = "The committee approved the plan.\nThe board then met\nwith the auditors on Friday."
    chunks = chunk_structured([PageText(1, text)], 900, 150)
    assert chunks[0].text.startswith("The committee approved the plan. The board then met with the auditors")


def test_long_sections_split_on_sentences_with_overlap():
    body = " ".join(f"Sentence {i} covers one detail of the warranty." for i in range(40))
    chunks = chunk_structured([PageText(1, "Warranty\n" + body)], 300, 80)
    assert len(chunks) > 3 and all(len(c.text) <= 300 for c in chunks)
    assert all(c.text.startswith("Warranty\nSentence") and c.text.endswith(".") for c in chunks)
    first_last = chunks[0].text.rsplit("Sentence", 1)[1]
    assert first_last in chunks[1].text


def test_table_units_are_split_on_whole_rows():
    rows = "\n".join(f"Row {i}: order_id: ORD-{i} | qty: {i}" for i in range(1, 60))
    chunks = chunk_structured([PageText(1, rows, label="Rows 1-59")], 300, 80)
    for c in chunks:
        assert all(line.startswith("Row ") for line in c.text.splitlines())


def test_fixed_chunker_is_still_available():
    assert chunk_fixed([PageText(1, "word " * 400)], 900, 150)


def test_evaluation_runs_end_to_end():
    root = Path(__file__).resolve().parents[1] / "eval"
    sys.path.insert(0, str(root))
    import run

    embed_docs, embed_query = run.hash_embedder()
    import json

    questions = [json.loads(l) for l in (root / "questions.jsonl").read_text().splitlines() if l.strip()]
    units = run.load_units()
    results = {}
    for name, opts in run.variants(False):
        doc = run.build_corpus(units, opts["structured"], embed_docs)
        rows, _ = run.evaluate(doc, questions, opts, embed_query, 8)
        results[name] = run.summarize(rows, 8)
    first, last = list(results.values())[0], list(results.values())[-1]
    assert last["MRR"] > first["MRR"] and last["R@8"] >= first["R@8"]
    assert all(r["unreachable"] == 0 for r in results.values())
