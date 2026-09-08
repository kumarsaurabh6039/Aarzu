from pathlib import Path

import google.generativeai as genai

from app.config import GEMINI_API_KEY, CHAT_MODEL
from app.rag.memory_search import search_memories
from app.rag.memory_extractor import extract_memory

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = Path(__file__).parent.parent / "prompts" / "aarzu_system.txt"
SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT.read_text()


def chat_with_aarzu(user_id: str, message: str) -> str:
    # 1. Retrieve relevant long-term memories
    memories = search_memories(user_id=user_id, query=message, limit=5) or []
    memory_text = "\n".join(f"- {m['content']}" for m in memories) or "(no relevant memories yet)"

    prompt = f"""PRIVATE USER MEMORIES:
{memory_text}

CURRENT USER MESSAGE:
{message}
"""

    model = genai.GenerativeModel(
        CHAT_MODEL,
        system_instruction=SYSTEM_PROMPT_TEXT,
    )
    response = model.generate_content(prompt)

    # 2. Fire-and-forget: check if this message should become a new memory
    try:
        extract_memory(user_id=user_id, message=message)
    except Exception:
        pass  # never let memory extraction break the chat response

    return response.text
