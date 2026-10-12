# Architecture

## Components

| Part | Tech | Role |
|---|---|---|
| Frontend | React, TypeScript, Vite | Upload, chat, history, sign-in, Contribute page |
| Backend | FastAPI | Auth check, file extraction, embedding, retrieval, quota, Gemini calls |
| Auth | Firebase Auth (Google) | Sign-in; the backend verifies ID tokens against Google's public certificates |
| History | Firestore | `users/{uid}/chats/{chatId}`, readable and writable only by the owner |
| LLM | Gemini (free tier) | Answers from retrieved excerpts |

## Request flow

1. **Upload** (`POST /upload`): identify the user (member by token, guest by IP), apply tier limits, extract text per page, slide or row group, chunk (900 characters, 150 overlap), embed all chunks locally, store in memory with a 2-hour life.
2. **Ask** (`POST /ask`): take one or more `doc_ids`. If the question names a file or a file type, narrow to those files. Embed the question, score chunks by cosine similarity, and pick the top chunks (8, or 16 spread across the document for broad questions like summaries). With several files, the budget is split across them and excerpts are labelled with the file name.
3. **Answer**: send excerpts and recent history to Gemini. If a model is busy or rate limited, try the next model in `GEMINI_MODELS`. Failures are refunded from the user's quota.

## Extraction

- PDF: PyMuPDF text; any page under 50 characters is rendered and read with Tesseract.
- Images: Tesseract.
- CSV/TSV/XLSX: summary statistics over all rows plus groups of rows; only the first rows are embedded (`EMBED_ROWS`).
- DOCX, PPTX, TXT, MD: text in parts; slides include speaker notes.

## Quota design

A daily budget is split into an 80% shared pool and a 20% reserve. Each active user's share is the pool divided by active users; users who arrive late use the reserve. Per-minute limits apply per user and globally. Guests also have daily question and upload caps. Counters reset at midnight Pacific, matching Google's quota reset.

## Frontend notes

- The app stays mounted while `/contribute` is shown, so an open chat is not lost.
- Stale-response guards (`session`, `uploadSeq`) stop slow uploads or answers from landing in a different chat.
- Answers are rendered with react-markdown, remark-gfm, remark-math and rehype-katex, loaded lazily to keep the first load small.
- No blur layers sit over the moving background; cards use translucent fills for speed.

## Known limits

In-memory document store and counters (single server instance), no cross-file comparison beyond retrieving from several files, weak handwriting OCR.
