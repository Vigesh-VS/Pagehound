import logging
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from . import config, embeddings, guard, llm, rerank
from .chunking import chunk_pages
from .auth import identify
from .extractors import UnsupportedType, extract, file_extension
from .pdf_utils import ExtractError
from .quota import quota
from .query import contextualize
from .retrieval import gather_sources, narrow_docs
from .store import store

processing = threading.Semaphore(config.PROCESS_SLOTS)
log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app):
    try:
        embeddings.warmup()
    except Exception as exc:
        print(f"Embedding model could not be loaded: {exc}")
    try:
        rerank.warmup()
    except Exception as exc:
        print(f"Reranker could not be loaded: {exc}")
    yield


app = FastAPI(title="Pagehound API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for key, value in SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str

    @field_validator("text")
    @classmethod
    def trim(cls, value):
        return value[:2000]


class AskBody(BaseModel):
    doc_id: str | None = None
    doc_ids: list[str] = Field(default_factory=list, max_length=6)
    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_CHARS)
    history: list[Turn] = Field(default_factory=list, max_length=10)


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": config.GEMINI_MODEL,
        "embedding_model": config.GEMINI_EMBED_MODEL if config.EMBED_BACKEND == "gemini" else config.EMBED_MODEL,
        "retrieval": {"hybrid": config.HYBRID, "mmr": config.MMR, "rewrite_follow_ups": config.REWRITE_FOLLOW_UPS, "structured_chunks": config.STRUCTURED_CHUNKS, "rerank": config.RERANK},
    }


@app.get("/quota")
def get_quota(request: Request):
    who = identify(request)
    return {**quota.status(who.id), "member": who.member}


@app.post("/upload")
def upload(request: Request, file: UploadFile = File(...)):
    who = identify(request)
    filename = file.filename or "document"

    if who.member:
        max_mb, max_pages, uploads = config.MEMBER_MAX_UPLOAD_MB, config.MEMBER_MAX_PAGES, config.MEMBER_UPLOADS_PER_DAY
    else:
        max_mb, max_pages, uploads = config.GUEST_MAX_UPLOAD_MB, config.GUEST_MAX_PAGES, config.GUEST_UPLOADS_PER_DAY
        if file_extension(filename) not in {".pdf", ""}:
            raise HTTPException(403, "Sign in with Google to upload this file type. Guests can upload PDFs.")

    if not quota.consume_upload(who.id, uploads):
        raise HTTPException(429, "You've reached today's upload limit.")

    limit = max_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        hint = "" if who.member else " Sign in with Google for larger files."
        raise HTTPException(413, f"File is larger than {max_mb} MB.{hint}")

    with processing:
        try:
            result = extract(filename, data, max_pages)
        except UnsupportedType as exc:
            raise HTTPException(415, str(exc))
        except ExtractError as exc:
            raise HTTPException(422, str(exc))

        chunks = chunk_pages(result.units, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        if not chunks:
            raise HTTPException(422, "No readable text was found in this file, even after OCR.")

        vectors = embeddings.embed_documents([c.text for c in chunks])

    doc = store.add(who.id, filename, chunks, vectors)
    return {
        "doc_id": doc.doc_id,
        "filename": doc.filename,
        "kind": result.kind,
        "pages": result.total_units,
        "pages_processed": len(result.units),
        "ocr_pages": [u.number for u in result.units if u.ocr],
        "chunks": len(chunks),
        "truncated": result.truncated,
        "member": who.member,
    }


@app.post("/ask")
def ask(request: Request, body: AskBody):
    who = identify(request)
    user = who.id
    wanted = list(dict.fromkeys([*body.doc_ids, *([body.doc_id] if body.doc_id else [])]))
    docs = [d for d in (store.get(i, (who.id, who.guest_id)) for i in wanted) if d is not None]
    if not docs:
        raise HTTPException(404, "Document not found or expired. Please upload it again.")
    docs = narrow_docs(docs, body.question)

    blocked = guard.classify(body.question)
    if blocked:
        log.warning("Blocked a %s attempt", blocked)
        return {"answer": guard.REFUSAL, "sources": [], "quota": quota.status(user), "blocked": True}

    cap = None if who.member else config.GUEST_QUESTIONS_PER_DAY
    decision = quota.check_and_consume(user, cap)
    if not decision.ok:
        headers = {"Retry-After": str(decision.retry_after)} if decision.retry_after else {}
        return JSONResponse(
            status_code=429,
            content={"message": decision.message, "reason": decision.reason, "quota": decision.status},
            headers=headers,
        )

    history = guard.safe_history([t.model_dump() for t in body.history])
    search = contextualize(body.question, history) if config.REWRITE_FOLLOW_UPS else body.question
    query_vector = embeddings.embed_query(search)
    sources = gather_sources(docs, query_vector, body.question, search)

    try:
        text = llm.answer(body.question, sources, [t.model_dump() for t in body.history])
    except llm.LLMError as exc:
        if not exc.rate_limited:
            quota.refund(user)
        return JSONResponse(
            status_code=503,
            content={"message": str(exc), "reason": "llm_error", "quota": quota.status(user)},
        )

    return {
        "answer": text,
        "sources": [
            {"page": s["page"], "label": s["label"], "snippet": s["text"][:240], "score": round(s["score"], 3)}
            for s in sources
        ],
        "quota": quota.status(user),
    }
