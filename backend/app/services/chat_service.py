from pathlib import Path

from google import genai

from app.config import GEMINI_API_KEY, CHAT_MODEL
from app.rag.memory_search import search_memories
from app.rag.memory_extractor import extract_memory


if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")


client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = Path(__file__).parent.parent / "prompts" / "aarzu_system.txt"
SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT.read_text(encoding="utf-8")


def chat_with_aarzu(user_id: str, message: str) -> str:
    # 1. Retrieve relevant long-term memories
    memories = search_memories(
        user_id=user_id,
        query=message,
        limit=5
    ) or []

    memory_text = "\n".join(
        f"- {m['content']}" for m in memories
    ) or "(no relevant memories yet)"

    prompt = f"""PRIVATE USER MEMORIES:
{memory_text}

CURRENT USER MESSAGE:
{message}
"""

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt,
        config={
            "system_instruction": SYSTEM_PROMPT_TEXT,
        }
    )

    # 2. Try to save useful long-term memory
    try:
        extract_memory(
            user_id=user_id,
            message=message
        )
    except Exception:
        pass

    return response.text