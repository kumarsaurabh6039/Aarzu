import os

from dotenv import load_dotenv

load_dotenv()

# =========================
# Supabase
# =========================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


# =========================
# AI API Keys
# =========================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# =========================
# AI Models
# =========================

# Primary AI
GROQ_CHAT_MODEL = os.getenv(
    "GROQ_CHAT_MODEL",
    "openai/gpt-oss-120b"
)

# Backup AI
GEMINI_CHAT_MODEL = os.getenv(
    "GEMINI_CHAT_MODEL",
    "gemini-2.0-flash"
)


# =========================
# Embeddings
# =========================

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "models/text-embedding-004"
)


# =========================
# Owner access
# =========================

# Anyone whose request carries this exact key in the
# X-Aarzu-Owner-Key header is treated as the owner (Saurabh).
# The client-sent "is_owner" flag is NEVER trusted directly.
OWNER_ACCESS_KEY = os.getenv("OWNER_ACCESS_KEY")


# =========================
# Application
# =========================

DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID")

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "*"
)