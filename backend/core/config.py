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
MEMORY_CASES_PATH = DATA_DIR / "memory_cases.json"  # saved cases (POST /api/cases)
LLM_CACHE_DIR = DATA_DIR / "llm_cache"

MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "local")  # only "local" exists; Hindsight adapter deferred
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # supports JSON mode
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").strip().lower() in ("1", "true", "yes")
LLM_TIMEOUT_S = 15
LLM_TEMPERATURE = 0.2

# Broad safety bounds, not anomaly thresholds. Seeded machine normal ranges are narrower.
PHYSICAL_RANGES = {"temperature": (-50, 500), "speed": (0, 10000), "vibration": (0, 100),
                   "motor_current": (0, 1000), "defect_count": (0, 1000000), "downtime_min": (0, 1440)}
UPLOAD_MAX_MB = float(os.getenv("UPLOAD_MAX_MB", "10"))
DOC_UPLOAD_MAX_MB = float(os.getenv("DOC_UPLOAD_MAX_MB", "20"))
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")]
APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
