# Progress log

## Done

- Pushed to GitHub, backend deployed on Render (Docker), frontend deployed on Vercel.
- Backend: upload and ask API, OCR fallback, multi-format extraction, local embeddings, retrieval with broad-question sampling.
- Quota manager with shared pool, reserve, per-minute limits and refunds.
- Model fallback across several Gemini models, with the real error logged.
- Firebase Google sign-in, ID-token verification, Firestore chat history with owner-only rules.
- Guest and member tiers with different file types, sizes and page limits.
- Multi-file chats with file-aware retrieval.
- Frontend: dark glass UI, aurora background, animated logo intro, greeting by time of day, loading file chip, history panel, new chat, Contribute page with UPI QR, mobile layout, PT Serif typography, math and table rendering.
- Answer styling: wider desktop layout, borderless mobile answers, boxed formulas and highlighted terms.
- A question interrupted by a refresh is asked again automatically after the page reloads.
- Retrieval quality: structure-aware chunking, hybrid BM25 + dense search with RRF, follow-up query rewriting, MMR, optional cross-encoder reranker, golden dataset with Recall@k and MRR evaluation. First real evaluation (bge-small): R@1 0.50 → 0.70, R@8 0.83 → 0.96, MRR 0.64 → 0.79; the one exact-code miss led to exact-identifier boosting. Fixed broad-question detection treating any question containing "about" as a summary request.
- Prompt-injection guardrails: input guard, fenced prompt, history filter, canary and leak check on replies, safe answer rendering.
- Resume updated with the live demo and GitHub links.
- Tests: backend 139 passing.

- Per-chat URLs so refresh, new tabs and back/forward behave like other chat apps; guest chats move into the account on sign-in.
- Retry on busy Gemini models; a failed question is put back in the input box.

## Next

- Run `eval/run.py --rerank --save` with the real embedding model and decide whether to enable the reranker on Render.

1. Confirm sign-in and uploads on the live site.
2. Add live and GitHub links to the resume.

## Later ideas

- Gemini vision for handwriting.
- Bring-your-own API key.
- Restore all files when reopening an old chat.
- Work-management AI agent project.
