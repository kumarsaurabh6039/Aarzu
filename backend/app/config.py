import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID")

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")

FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
