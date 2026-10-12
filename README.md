# Pagehound

Upload a document and ask questions about it. Pagehound reads PDFs (including scanned pages through OCR), images, spreadsheets, Word files, slides and text, finds the relevant parts with local embeddings, and answers with Google Gemini.

**Live app:** _add link after deployment_

## Features

- Reads PDF, PNG/JPG/WEBP/BMP/TIFF (OCR), CSV/TSV/XLSX, DOCX, PPTX, TXT and MD.
- Scanned PDF pages are detected automatically and read with Tesseract OCR.
- Retrieval-augmented answers: documents are chunked, embedded locally with `BAAI/bge-small-en-v1.5`, and the best chunks are sent to Gemini.
- Several files in one chat. Questions search all files in the chat, or only the file or file type you mention.
- Math in answers is rendered with KaTeX; tables render as tables.
- Google sign-in with Firebase. Signed-in users keep chat history (Firestore, owner-only rules) and get larger limits.
- Guests can upload PDFs up to 10 MB and 25 pages. Signed-in users can upload all file types with higher limits.
- Free-tier quota manager that shares a daily Gemini budget fairly between active users.
- Dark, glass-style interface with an animated intro, responsive down to phone width.

## How it works

```
Browser (React + Vite)  --upload/ask-->  FastAPI backend  --prompt-->  Gemini
        |                                   |
   Firebase Auth / Firestore          extract -> chunk -> embed -> retrieve
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details and [docs/PROGRESS.md](docs/PROGRESS.md) for the build log.

## Run locally

Backend (Windows PowerShell):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Fill `GEMINI_API_KEY` (free key from Google AI Studio) and `FIREBASE_PROJECT_ID` in `backend/.env`. Install Tesseract if you want OCR.

Frontend:

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Fill the `VITE_FIREBASE_*` values from your Firebase web app. Add the frontend address to `ALLOWED_ORIGINS` in the backend `.env`.

Firestore rules are in `firestore.rules`.

## Tests

```powershell
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

## Tech stack

Python, FastAPI, PyMuPDF, Tesseract, fastembed, NumPy, Google Gemini, React, TypeScript, Vite, Firebase Auth and Firestore, KaTeX.

## Limitations

- Uploaded documents are kept in server memory for 2 hours; quota counters reset when the server restarts.
- Handwriting OCR is weak. Printed scans work well.
- Free Gemini tiers can be busy; the backend falls back through a list of models.

Made by Vigesh.
