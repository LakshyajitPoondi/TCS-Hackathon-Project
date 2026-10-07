"""Paths, column names and shared constants. Column names are defined here only."""

from pathlib import Path

API_NAME = "Production Intelligence & RCA API"
API_VERSION = "0.1.0"

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
INCIDENTS_DIR = DATA_DIR / "incidents"
UPLOADS_DIR = DATA_DIR / "uploads"

EXPECTED_COLUMNS = [
    "timestamp", "line", "machine", "event_code", "temperature", "speed",
    "vibration", "motor_current", "defect_count", "downtime_min", "batch", "operator_note",
]
NUMERIC_COLUMNS = ["temperature", "speed", "vibration", "motor_current", "defect_count", "downtime_min"]
TEXT_COLUMNS = ["line", "machine", "event_code", "batch", "operator_note"]

# A numeric column is rejected when more than this share of its non-empty values can't be parsed.
MAX_UNPARSEABLE_FRACTION = 0.5

CORS_ORIGINS = ["http://localhost:5173"]

WARNING = (
    "These are hypotheses, not confirmed root causes. "
    "Engineering validation is required before corrective action."
)

# ---------- Phase 3: knowledge, memory, LLM ----------
import os  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT_DIR / ".env")

SOPS_DIR = DATA_DIR / "sops"
MEMORY_SEED_PATH = DATA_DIR / "memory_seed.json"   # read-only
LLM_CACHE_DIR = DATA_DIR / "llm_cache"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").strip().lower() in ("1", "true", "yes")

# Broad safety bounds, not anomaly thresholds. Seeded machine normal ranges are narrower.
PHYSICAL_RANGES = {"temperature": (-50, 500), "speed": (0, 10000), "vibration": (0, 100),
                   "motor_current": (0, 1000), "defect_count": (0, 1000000), "downtime_min": (0, 1440)}
UPLOAD_MAX_MB = float(os.getenv("UPLOAD_MAX_MB", "10"))
DOC_UPLOAD_MAX_MB = float(os.getenv("DOC_UPLOAD_MAX_MB", "20"))
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")]
APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://rca:rca@localhost:5433/rca")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def resolve_llm_key(provider, llm_api_key, groq_api_key):
    """LLM_API_KEY for every provider; GROQ_API_KEY only for groq when LLM_API_KEY is empty/blank.
    Returns (key, source variable name or None). Never logs the key itself."""
    if (llm_api_key or "").strip():
        return llm_api_key.strip(), "LLM_API_KEY"
    if provider == "groq" and (groq_api_key or "").strip():
        return groq_api_key.strip(), "GROQ_API_KEY"
    return "", None


LLM_API_KEY, LLM_KEY_SOURCE = resolve_llm_key(LLM_PROVIDER, os.getenv("LLM_API_KEY", ""), GROQ_API_KEY)
import logging as _logging  # noqa: E402
_logging.getLogger("rca.config").info("LLM provider=%s key_source=%s", LLM_PROVIDER, LLM_KEY_SOURCE or "none")
if not LLM_API_KEY and GROQ_API_KEY and LLM_PROVIDER != "groq":
    _logging.getLogger("rca.config").warning(
        "GROQ_API_KEY is set but LLM_PROVIDER=%s reads only LLM_API_KEY; move the key to LLM_API_KEY.", LLM_PROVIDER)
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"  # default for LLM_PROVIDER=gemini
LLM_BASE_URL = os.getenv("LLM_BASE_URL", {"groq": "https://api.groq.com/openai/v1", "gemini": GEMINI_BASE_URL}.get(LLM_PROVIDER, ""))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "15"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))
AGENT_ENABLED = os.getenv("AGENT_ENABLED", "true").lower() == "true"
# deterministic: fixed read-only tool sequence, no LLM calls. llm_plan: ONE LLM call returns the whole tool plan.
AGENT_MODE = os.getenv("AGENT_MODE", "deterministic").strip().lower()
if AGENT_MODE not in ("deterministic", "llm_plan"):
    AGENT_MODE = "deterministic"
# Live provider requests allowed per UTC day (counted in the database) and per analysis (plan + wording).
LLM_DAILY_BUDGET = max(0, int(os.getenv("LLM_DAILY_BUDGET", "18")))
LLM_MAX_CALLS_PER_ANALYSIS = max(0, int(os.getenv("LLM_MAX_CALLS_PER_ANALYSIS", "2")))
# Test-only: what the fake provider returns (ok | quota | rate_limit | 503 | 503_once | invalid_json).
LLM_FAKE_SCENARIO = os.getenv("LLM_FAKE_SCENARIO", "ok").strip().lower()
AGENT_MAX_STEPS = max(1, min(30, int(os.getenv("AGENT_MAX_STEPS", "10"))))
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "") or DATA_DIR / "documents")
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "fastembed").strip().lower()
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDINGS_API_KEY = os.getenv("EMBEDDINGS_API_KEY", "")
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "")
RAG_TOP_K = max(1, min(20, int(os.getenv("RAG_TOP_K", "4"))))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0"))
JUDGE_ENABLED = os.getenv("JUDGE_ENABLED", "false").lower() == "true"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", LLM_MODEL)
