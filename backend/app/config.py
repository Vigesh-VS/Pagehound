import os
from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    return int(os.getenv(name, default))


def _float(name, default):
    return float(os.getenv(name, default))


ENV = os.getenv("ENV", "dev")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", GEMINI_MODEL).split(",") if m.strip()]
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "local").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GEMINI_EMBED_DIMS = _int("GEMINI_EMBED_DIMS", 768)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

DAILY_BUDGET = _int("DAILY_BUDGET", 100)
RESERVE_FRACTION = _float("RESERVE_FRACTION", 0.2)
GLOBAL_RPM = _int("GLOBAL_RPM", 8)
USER_RPM = _int("USER_RPM", 3)
UPLOADS_PER_DAY = _int("UPLOADS_PER_DAY", 5)

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 10)
MAX_PAGES = _int("MAX_PAGES", 50)

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
GUEST_MAX_UPLOAD_MB = _int("GUEST_MAX_UPLOAD_MB", 10)
GUEST_MAX_PAGES = _int("GUEST_MAX_PAGES", 25)
GUEST_QUESTIONS_PER_DAY = _int("GUEST_QUESTIONS_PER_DAY", 10)
GUEST_UPLOADS_PER_DAY = _int("GUEST_UPLOADS_PER_DAY", 3)
MEMBER_MAX_UPLOAD_MB = _int("MEMBER_MAX_UPLOAD_MB", 50)
MEMBER_MAX_PAGES = _int("MEMBER_MAX_PAGES", 100)
MEMBER_UPLOADS_PER_DAY = _int("MEMBER_UPLOADS_PER_DAY", 30)
OCR_MIN_CHARS = _int("OCR_MIN_CHARS", 50)
OCR_DPI = _int("OCR_DPI", 200)
PROCESS_SLOTS = _int("PROCESS_SLOTS", 2)
MAX_ROWS = _int("MAX_ROWS", 50000)
EMBED_ROWS = _int("EMBED_ROWS", 1500)
ROWS_PER_UNIT = _int("ROWS_PER_UNIT", 20)
MAX_UNITS = _int("MAX_UNITS", 300)
TEXT_UNIT_CHARS = _int("TEXT_UNIT_CHARS", 3000)
MAX_IMAGE_PIXELS = _int("MAX_IMAGE_PIXELS", 40_000_000)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = 8
BROAD_TOP_K = 16
HYBRID = os.getenv("HYBRID", "1") != "0"
MMR = os.getenv("MMR", "1") != "0"
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.75"))
REWRITE_FOLLOW_UPS = os.getenv("REWRITE_FOLLOW_UPS", "1") != "0"
STRUCTURED_CHUNKS = os.getenv("STRUCTURED_CHUNKS", "1") != "0"
RERANK = os.getenv("RERANK", "0") == "1"
RERANK_MODEL = os.getenv("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
RERANK_CANDIDATES = _int("RERANK_CANDIDATES", 20)
MAX_QUESTION_CHARS = 1000
DOC_TTL_SECONDS = 2 * 60 * 60
MAX_DOCS = 50
