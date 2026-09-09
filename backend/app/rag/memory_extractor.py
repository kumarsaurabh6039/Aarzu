import json
import re

from google import genai

from app.config import GEMINI_API_KEY, CHAT_MODEL
from app.rag.memory_writer import save_memory

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=GEMINI_API_KEY)

MEMORY_PROMPT = """You are a personal memory extraction system.

Analyze the user's message and decide if it contains something worth
remembering about them long-term.

Good memories: goals, career plans, technical skills, preferences,
important personal facts, long-term plans, important experiences,
recurring problems, decisions.

Do NOT store: random temporary statements, passwords, API keys, card
numbers, or unnecessary sensitive information.

Return ONLY raw JSON, no markdown fences, in this exact format:
{"should_save": true, "memory": "short useful memory", "memory_type": "goal", "importance": 8}

If nothing is worth saving, return:
{"should_save": false}

User message:
"""


def extract_memory(user_id: str, message: str):
    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=MEMORY_PROMPT + message,
    )

    text = response.text.strip()

    # Remove markdown code fences if Gemini returns them
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not data.get("should_save"):
        return None

    memory = data.get("memory")

    if not memory:
        return None

    save_memory(
        user_id=user_id,
        content=memory,
        memory_type=data.get("memory_type", "general"),
        importance=data.get("importance", 5),
    )

    return data