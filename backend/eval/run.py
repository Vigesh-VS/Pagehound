import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from app import config  # noqa: E402
from app.chunking import chunk_pages  # noqa: E402
from app.extractors import extract  # noqa: E402
from app.query import contextualize  # noqa: E402
from app.retrieval import select  # noqa: E402
from app.store import Document  # noqa: E402

BASE = dict(structured=False, hybrid=False, rewrite=False, mmr=False, rerank=False)
STEPS = [
    ("Baseline: fixed chunks, dense only", {}),
    ("+ structure-aware chunking", dict(structured=True)),
    ("+ hybrid search (BM25 + RRF)", dict(hybrid=True)),
    ("+ follow-up query rewriting", dict(rewrite=True)),
    ("+ MMR diversity", dict(mmr=True)),
    ("+ cross-encoder reranking", dict(rerank=True)),
]
TYPES = ["semantic", "exact", "follow_up"]


def variants(with_rerank):
    current, out = dict(BASE), []
    for name, change in STEPS:
        if change.get("rerank") and not with_rerank:
            continue
        current = {**current, **change}
        out.append((name, dict(current)))
    return out


def hash_embedder(dims=1024):
    def vec(text):
        words = [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split()]
        grams = words + [f"{a} {b}" for a, b in zip(words, words[1:])]
        v = np.zeros(dims, dtype=np.float32)
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            v[h % dims] += 1.0 if (h >> 20) & 1 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    return (lambda texts: np.array([vec(t) for t in texts])), vec


def app_embedder():
    from app import embeddings

    return embeddings.embed_documents, embeddings.embed_query


def load_units():
    units = []
    for path in sorted((ROOT / "docs").iterdir()):
        units.append(extract(path.name, path.read_bytes()).units)
    return units


def build_corpus(units, structured, embed_docs):
    chunks = []
    for doc_units in units:
        chunks.extend(chunk_pages(doc_units, config.CHUNK_SIZE, config.CHUNK_OVERLAP, structured))
    vectors = embed_docs([c.text for c in chunks])
    return Document("eval", "eval", "corpus", chunks, vectors)


def norm(text):
    return " ".join(text.split()).lower()


def evaluate(doc, questions, opts, embed_query, k):
    texts = [norm(c.text) for c in doc.chunks]
    rows, cache, spent = [], {}, 0.0
    for q in questions:
        golds = [norm(g) for g in q["gold"]]
        history = [{"role": "user", "text": h} for h in q["history"]]
        search = contextualize(q["question"], history) if opts["rewrite"] else q["question"]
        if search not in cache:
            cache[search] = embed_query(search)
        start = time.perf_counter()
        picked, _ = select(doc, cache[search], search, q["question"], k, hybrid=opts["hybrid"], mmr=opts["mmr"], rerank=opts["rerank"])
        spent += time.perf_counter() - start
        rank = next((p + 1 for p, i in enumerate(picked) if any(g in texts[i] for g in golds)), None)
        reachable = any(g in t for g in golds for t in texts)
        rows.append({"type": q["type"], "rank": rank, "reachable": reachable, "question": q["question"]})
    return rows, 1000 * spent / max(len(questions), 1)


def summarize(rows, k):
    def recall(subset, n):
        return sum(1 for r in subset if r["rank"] and r["rank"] <= n) / max(len(subset), 1)

    mrr = sum(1 / r["rank"] for r in rows if r["rank"]) / max(len(rows), 1)
    out = {"R@1": recall(rows, 1), "R@3": recall(rows, 3), f"R@{k}": recall(rows, k), "MRR": mrr}
    for t in TYPES:
        out[f"{t} R@3"] = recall([r for r in rows if r["type"] == t], 3)
    out["unreachable"] = sum(1 for r in rows if not r["reachable"])
    return out


def main():
    parser = argparse.ArgumentParser(description="Measure Pagehound retrieval quality on the golden dataset.")
    parser.add_argument("--embedder", choices=["app", "hash"], default="app", help="app uses the real embedding backend from .env; hash is an offline stand-in for smoke tests")
    parser.add_argument("--rerank", action="store_true", help="also evaluate the cross-encoder reranker (downloads the model on first run)")
    parser.add_argument("--k", type=int, default=config.TOP_K)
    parser.add_argument("--save", action="store_true", help="write the table to eval/results.md")
    parser.add_argument("--misses", action="store_true", help="list questions the final setup missed")
    args = parser.parse_args()

    embed_docs, embed_query = app_embedder() if args.embedder == "app" else hash_embedder()
    if args.rerank:
        from app.rerank import rerank as warm

        warm("warm up", ["the reranker is loaded before timing starts"])
    questions = [json.loads(line) for line in (ROOT / "questions.jsonl").read_text().splitlines() if line.strip()]
    units = load_units()
    corpora = {}

    results = []
    for name, opts in variants(args.rerank):
        if opts["structured"] not in corpora:
            corpora[opts["structured"]] = build_corpus(units, opts["structured"], embed_docs)
        doc = corpora[opts["structured"]]
        rows, ms = evaluate(doc, questions, opts, embed_query, args.k)
        results.append((name, summarize(rows, args.k), ms, len(doc.chunks), rows))

    keys = list(results[0][1].keys())
    header = "| Setup | Chunks | " + " | ".join(keys) + " | ms/query |"
    lines = [header, "|" + "---|" * (len(keys) + 3)]
    for name, stats, ms, chunks, _ in results:
        cells = [str(stats[key]) if key == "unreachable" else f"{stats[key]:.2f}" for key in keys]
        lines.append(f"| {name} | {chunks} | " + " | ".join(cells) + f" | {ms:.1f} |")
    title = f"Embedder: {'hash stand-in (offline, not meaningful for semantic questions)' if args.embedder == 'hash' else (config.GEMINI_EMBED_MODEL if config.EMBED_BACKEND == 'gemini' else config.EMBED_MODEL)} · {len(questions)} questions · k={args.k}"
    table = "\n".join([title, "", *lines])
    print(table)

    if args.misses:
        print("\nMissed by the final setup:")
        for r in results[-1][4]:
            if not r["rank"] or r["rank"] > 3:
                print(f"  [{r['type']}] {r['question']} -> rank {r['rank']}")

    if args.save:
        (ROOT / "results.md").write_text(f"# Retrieval evaluation results\n\n{table}\n")


if __name__ == "__main__":
    main()
