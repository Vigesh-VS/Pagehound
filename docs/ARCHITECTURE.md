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
3. **Answer**: send excerpts and recent history to Gemini. A busy model is retried twice, then the next model in `GEMINI_MODELS` is tried. Failures are refunded from the user's quota.

## Extraction

- PDF: PyMuPDF text; any page under 50 characters is rendered and read with Tesseract.
- Images: Tesseract.
- CSV/TSV/XLSX: summary statistics over all rows plus groups of rows; only the first rows are embedded (`EMBED_ROWS`).
- DOCX, PPTX, TXT, MD: text in parts; slides include speaker notes.

## Quota design

A daily budget is split into an 80% shared pool and a 20% reserve. Each active user's share is the pool divided by active users; users who arrive late use the reserve. Per-minute limits apply per user and globally. Guests also have daily question and upload caps. Counters reset at midnight Pacific, matching Google's quota reset.

## Retrieval

1. Upload: `chunk_structured` splits each page into sections at detected headings, packs whole sentences up to 900 characters with about 150 characters of overlap, prefixes each chunk with its heading and merges very small neighbours. Table units are packed by whole rows.
2. Ask: `query.split_questions` splits a message with several questions (up to 8 parts); each part is joined with the previous question when it is a follow-up (`query.contextualize`) and embedded separately. `retrieval.gather_many` retrieves for each part and removes duplicates.
3. `retrieval.rank` orders chunks by cosine similarity and, with `HYBRID`, by BM25 as well, fusing the two with Reciprocal Rank Fusion (k = 60). The BM25 index is built on the first question and cached on the document. Chunks containing an identifier from the question such as `ORD-1089` or `E5` are then moved to the front (skipped when the code appears in more than a quarter of the chunks).
4. With `RERANK=1`, the top 20 are re-scored by the `ms-marco-MiniLM-L-6-v2` cross-encoder (baked into the Docker image).
5. `retrieval.choose` takes the top 8 (or 16 spread across the file for broad questions), using MMR (λ = 0.75) to skip near-duplicates, and sends them in reading order.
6. `eval/run.py` measures Recall@k and MRR for each step on the golden dataset.

## Prompt-injection defences

1. `guard.classify` refuses prompt-extraction and override attempts before quota or the model is used.
2. `llm.build_prompt` fences untrusted text in tagged blocks and `guard.neutralize` strips spoofed tags.
3. `guard.safe_history` drops injected user turns from the client-supplied history.
4. The system prompt marks all fenced text as data and the instructions as confidential.
5. `guard.leaks` checks every reply for the canary or copied instruction text, ignoring text that also appears in the retrieved excerpts.
6. `Answer.tsx` renders no images or raw HTML and only safe `http(s)` links.

## Privacy and hardening

- `ENV` defaults to `production`; the `x-debug-user` header used by tests works only with `ENV=dev`.
- Security headers come from `vercel.json` for the site and a FastAPI middleware for the API (`nosniff`, `DENY` framing, referrer policy, `no-store`).
- A notice under the input explains the 2-hour file lifetime and that Google's free Gemini tier may use and review content.
- Known gap: guest identity uses the first `X-Forwarded-For` entry, which a client can set. Render appends its own entry rather than replacing the header, so the safe entry needs confirming against real Render traffic before changing it. Impact is limited because document IDs are random and the global quota still applies.

## Frontend notes

- Every chat has its own address (`/c/<id>`), like other chat apps. Refreshing a tab keeps that tab's chat, a new tab starts on the home screen, and back/forward move between chats. Each chat is also cached in the browser under its own key (guest chats included); signed-in chats are saved in Firestore, and a guest chat is moved into the account on sign-in.
- The app stays mounted while `/contribute` is shown, so an open chat is not lost.
- Stale-response guards (`session`, `uploadSeq`) stop slow uploads or answers from landing in a different chat.
- Answers are rendered with react-markdown, remark-gfm, remark-math and rehype-katex, loaded lazily to keep the first load small.
- No blur layers sit over the moving background; cards use translucent fills for speed.

## Known limits

In-memory document store and counters (single server instance), no cross-file comparison beyond retrieving from several files, weak handwriting OCR.
