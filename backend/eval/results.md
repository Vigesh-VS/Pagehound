# Retrieval evaluation results

Embedder: BAAI/bge-small-en-v1.5 · 46 questions · k=8 · run on a Windows laptop CPU. Each row adds one technique to the row above.

| Setup | Chunks | R@1 | R@3 | R@8 | MRR | semantic R@3 | exact R@3 | follow_up R@3 | unreachable | ms/query |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline: fixed chunks, dense only | 50 | 0.50 | 0.78 | 0.83 | 0.64 | 0.89 | 0.64 | 0.57 | 0 | 0.1 |
| + structure-aware chunking | 48 | 0.63 | 0.80 | 0.85 | 0.72 | 0.93 | 0.73 | 0.43 | 0 | 0.1 |
| + hybrid search (BM25 + RRF) | 48 | 0.67 | 0.85 | 0.96 | 0.77 | 0.82 | 1.00 | 0.71 | 0 | 1.0 |
| + follow-up query rewriting | 48 | 0.72 | 0.89 | 0.98 | 0.81 | 0.82 | 1.00 | 1.00 | 0 | 0.7 |
| + MMR diversity | 48 | 0.72 | 0.91 | 0.98 | 0.82 | 0.86 | 1.00 | 1.00 | 0 | 2.5 |
| + cross-encoder reranking | 48 | 0.85 | 0.93 | 0.98 | 0.90 | 0.89 | 1.00 | 1.00 | 0 | 1506.1 |

ms/query covers ranking only (not embedding the question). The live site runs everything up to MMR; the reranker is available with `RERANK=1` but adds about 1.5 s per question on a laptop and far more on the free server.

Still missed by the full setup: "Is extra work paid more?" (rank 5), "How quiet is the purifier at night?" (rank 5) and "What happens to my coverage if water gets inside?" (not retrieved; the document says "warranty is void… damaged by liquid", with no shared words).
