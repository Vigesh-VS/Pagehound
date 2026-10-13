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

## OCR check

```powershell
python eval/ocr_check.py --save
```

Counts how many known facts OCR recovers from each scanned page of `ocr/helios_test_report.pdf` and how long extraction takes. Results go to `ocr_results.md`.

## Answer quality

```powershell
python eval/answers.py --limit 5    # quick try
python eval/answers.py --save       # full run, writes answer_results.md
```

`answer_set.jsonl` holds 25 questions with reference answers and `must` phrases. For each one the script runs the same retrieval as the API (`app/pipeline.py`), asks Gemini for the answer, then asks Gemini again, at temperature 0, to act as a judge. Text from documents and answers is fenced so it cannot instruct the judge.

- **Key facts present:** share of answerable questions whose answer contains every `must` phrase.
- **Faithfulness (1-5):** are all claims supported by the excerpts? Low scores mean hallucination.
- **Correctness (1-5):** does the answer agree with the reference?
- **Answered when it should / Said "not found" when it should:** catches both over-refusal and made-up answers.

An LLM judge is itself a model and can be wrong, so read the "Needs a look" list rather than trusting one number. `--judge-model` lets you use a stronger model as the judge than the one that wrote the answers.
