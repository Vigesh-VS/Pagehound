# Progress log

## Done

- Backend: upload and ask API, OCR fallback, multi-format extraction, local embeddings, retrieval with broad-question sampling.
- Quota manager with shared pool, reserve, per-minute limits and refunds.
- Model fallback across several Gemini models, with the real error logged.
- Firebase Google sign-in, ID-token verification, Firestore chat history with owner-only rules.
- Guest and member tiers with different file types, sizes and page limits.
- Multi-file chats with file-aware retrieval.
- Frontend: dark glass UI, aurora background, animated logo intro, greeting by time of day, loading file chip, history panel, new chat, Contribute page with UPI QR, mobile layout, PT Serif typography, math and table rendering.
- Tests: backend 66 passing.

## Next

1. Push to GitHub.
2. Deploy backend (free host with Tesseract) and frontend (Vercel).
3. Set `ALLOWED_ORIGINS` and `FIREBASE_PROJECT_ID` on the host and add the live domain to Firebase authorized domains.
4. Add live and GitHub links to the resume.

## Later ideas

- Gemini vision for handwriting.
- Bring-your-own API key.
- Restore all files when reopening an old chat.
- Work-management AI agent project.
