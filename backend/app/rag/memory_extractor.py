import json
import re

import google.generativeai as genai

from app.config import GEMINI_API_KEY, CHAT_MODEL
from app.rag.memory_writer import save_memory

genai.configure(api_key=GEMINI_API_KEY)

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
    model = genai.GenerativeModel(CHAT_MODEL)
    response = model.generate_content(MEMORY_PROMPT + message)

    text = response.text.strip()
    text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not data.get("should_save"):
        return None

    save_memory(
        user_id=user_id,
        content=data["memory"],
        memory_type=data.get("memory_type", "general"),
        importance=data.get("importance", 5),
    )

    return data
