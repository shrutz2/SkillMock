"""Central configuration, loaded from environment variables (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Server ---
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    # --- Database ---
    # DB_BACKEND = "mysql" (as per architecture) or "sqlite" (zero-setup demo mode)
    DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "ai_mock_interviewer")
    SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "ai_mock.db"))

    # --- Embeddings ---
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    # "onnx" (fastembed, ~50 MB) or "torch" (sentence-transformers, ~1.5 GB).
    # Same model and identical vectors either way.
    EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "onnx")

    # --- LLM ---
    # LLM_PROVIDER = "groq" | "gemini" | "mock"
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # --- Interview ---
    QUESTIONS_PER_SESSION = int(os.getenv("QUESTIONS_PER_SESSION", "10"))
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
    # Retrieval unit: "bullet" (one chunk per accomplishment, ~20-40 per resume)
    # or "section" (one chunk per section, ~5-8). Section chunks make a top-3
    # search return most of the document, so bullet is the default.
    CHUNK_GRANULARITY = os.getenv("CHUNK_GRANULARITY", "bullet").lower()
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

    # --- Security ---
    # Comma-separated list of origins allowed to call the API from a browser.
    ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]
    # Sessions older than this are purged by the retention job.
    RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
