# Pagehound backend

FastAPI service: upload a document, search it with local embeddings, and get Gemini answers with citations.

## Supported files

| Type | How it is read | Citation label |
|---|---|---|
| PDF | Text layer, with OCR on scanned pages | Page 4 |
| PNG, JPG, WEBP, BMP, TIFF | OCR | Image |
| CSV, TSV, XLSX | Summary statistics plus rows in groups of 20 | Summary, Rows 1-20, Sheet rows 1-20 |
| DOCX, TXT, MD | Text in parts of about 3000 characters | Part 2 |
| PPTX | Slide text and speaker notes | Slide 3 |

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs to try the API. The first start downloads the embedding model.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Service and model info |
| GET | /quota | Your daily quota status |
| POST | /upload | Upload a file (OCR is used for scanned pages and images) |
| POST | /ask | Ask a question about one or more uploaded files (`doc_ids`) |

## Quota design

A daily budget of Gemini requests is split in two: an 80% shared pool and a 20% reserve for latecomers. A lone user can use the whole pool. Each active user's share is pool / active users, so it shrinks as people join. Users who arrive after the pool is spent draw from the reserve. Per-minute limits apply per user and globally. Counters reset at midnight Pacific, when Google's daily quota resets.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
