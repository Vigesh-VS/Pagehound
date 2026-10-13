# Retrieval evaluation

A small golden dataset for measuring how well Pagehound finds the right excerpts.

- `docs/`: four sample documents: an employee handbook, an air purifier manual, research notes and an orders table.
- `questions.jsonl`: 46 labelled questions. Each has a `type` (`semantic` for paraphrased wording, `exact` for codes and numbers, `follow_up` for questions that need the previous question), an optional `history`, and one or more `gold` phrases. A retrieved chunk counts as a hit if it contains a gold phrase.
- `run.py`: builds the corpus, then adds one retrieval technique at a time and prints Recall@1, Recall@3, Recall@8, MRR, per-type Recall@3, the number of questions whose answer was cut across chunks (`unreachable`) and the time per query.

## Run

```powershell
cd backend
python eval/run.py                    # real embedding backend from .env
python eval/run.py --rerank           # also test the cross-encoder reranker
python eval/run.py --misses           # list questions the final setup missed
python eval/run.py --save             # write results.md
python eval/run.py --embedder hash    # offline smoke test with a word-hashing stand-in
```

The `hash` embedder only matches words, so its numbers say nothing about semantic search. Use it to check the pipeline runs, not to judge quality.

## Metrics

- **Recall@k**: the share of questions where a chunk containing the answer is among the top k retrieved.
- **MRR (Mean Reciprocal Rank)**: the average of 1 / rank of the first correct chunk (1.0 if always first, 0.5 if always second, 0 if never found).

The dataset is small and synthetic, so treat the numbers as a regression check and a way to compare settings, not as a benchmark.
