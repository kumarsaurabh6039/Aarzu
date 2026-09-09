import json
import re

from groq import Groq
from google import genai

from app.config import (
    GROQ_API_KEY,
    GROQ_CHAT_MODEL,
    GEMINI_API_KEY,
    GEMINI_CHAT_MODEL,
)

from app.rag.memory_writer import save_memory


# =========================================================
# AI CLIENTS
# =========================================================

groq_client = None
gemini_client = None


if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )


if GEMINI_API_KEY:
    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )


# =========================================================
# MEMORY PROMPT
# =========================================================

MEMORY_PROMPT = """
You are Aarzu's long-term memory extraction system.

Analyze the user's message and decide whether it contains
information that is useful to remember about the user long-term.

SAVE information such as:

- long-term goals
- career plans
- technical skills
- learning plans
- stable preferences
- important personal facts
- important projects
- important decisions
- recurring problems
- long-term plans
- meaningful experiences

DO NOT SAVE:

- greetings
- casual conversation
- temporary statements
- random questions
- passwords
- API keys
- tokens
- card numbers
- financial credentials
- unnecessary sensitive information

IMPORTANT:

Only save information that is genuinely useful for future conversations.

Keep the memory short and useful.
Do not copy the entire user message.

Return ONLY valid JSON.

If the message contains useful long-term memory:

{
  "should_save": true,
  "memory": "short useful memory",
  "memory_type": "goal",
  "importance": 8
}

If there is nothing worth remembering:

{
  "should_save": false
}

User message:
"""


# =========================================================
# JSON PARSER
# =========================================================

def _parse_memory_response(text: str):

    if not text:
        return None

    text = text.strip()

    # Remove markdown code fences
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    text = text.strip()

    try:
        data = json.loads(text)

    except json.JSONDecodeError:

        print(
            "Memory extractor returned invalid JSON"
        )

        return None

    if not isinstance(data, dict):
        print(
            "Memory extractor returned non-object JSON"
        )
        return None

    return data


# =========================================================
# GROQ MEMORY EXTRACTION
# =========================================================

def _extract_with_groq(message: str):

    if not groq_client:
        return None

    try:

        response = groq_client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": MEMORY_PROMPT,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            temperature=0,
            response_format={
                "type": "json_object"
            },
        )

        text = response.choices[0].message.content

        return _parse_memory_response(text)

    except Exception as e:

        print(
            f"Groq memory extraction error: {e}"
        )

        return None


# =========================================================
# GEMINI MEMORY EXTRACTION FALLBACK
# =========================================================

def _extract_with_gemini(message: str):

    if not gemini_client:
        return None

    try:

        response = gemini_client.models.generate_content(
            model=GEMINI_CHAT_MODEL,
            contents=MEMORY_PROMPT + message,
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

        text = response.text

        return _parse_memory_response(text)

    except Exception as e:

        print(
            f"Gemini memory extraction error: {e}"
        )

        return None


# =========================================================
# MEMORY VALIDATION
# =========================================================

def _validate_memory(data):

    if not isinstance(data, dict):
        return None

    should_save = data.get("should_save")

    if should_save is not True:
        return None

    memory = data.get("memory")

    if not isinstance(memory, str):
        return None

    memory = memory.strip()

    if not memory:
        return None

    # Prevent accidentally storing huge memories
    memory = memory[:500]

    memory_type = data.get(
        "memory_type",
        "general",
    )

    if not isinstance(memory_type, str):
        memory_type = "general"

    memory_type = memory_type.strip().lower()

    if not memory_type:
        memory_type = "general"

    importance = data.get(
        "importance",
        5,
    )

    try:

        importance = int(importance)

    except (TypeError, ValueError):

        importance = 5

    importance = max(
        1,
        min(10, importance),
    )

    return {
        "should_save": True,
        "memory": memory,
        "memory_type": memory_type,
        "importance": importance,
    }


# =========================================================
# MAIN MEMORY EXTRACTION
# =========================================================

def extract_memory(
    user_id: str,
    message: str,
):

    if not message or not message.strip():
        return None

    data = None

    # -----------------------------------------------------
    # 1. GROQ PRIMARY
    # -----------------------------------------------------

    if groq_client:

        data = _extract_with_groq(message)

        if data is not None:

            print(
                "Memory extraction provider: Groq"
            )


    # -----------------------------------------------------
    # 2. GEMINI FALLBACK
    # -----------------------------------------------------

    if data is None and gemini_client:

        data = _extract_with_gemini(message)

        if data is not None:

            print(
                "Memory extraction provider: Gemini"
            )


    # -----------------------------------------------------
    # 3. BOTH PROVIDERS FAILED
    # -----------------------------------------------------

    if data is None:

        print(
            "Memory extraction failed on both providers"
        )

        return None


    # -----------------------------------------------------
    # 4. VALIDATE
    # -----------------------------------------------------

    validated = _validate_memory(data)

    if validated is None:

        return None


    # -----------------------------------------------------
    # 5. SAVE TO SUPABASE
    # -----------------------------------------------------

    try:

        save_memory(
            user_id=user_id,
            content=validated["memory"],
            memory_type=validated["memory_type"],
            importance=validated["importance"],
        )

        print(
            "Long-term memory saved"
        )

    except Exception as e:

        print(
            f"Memory save error: {e}"
        )

        return None


    # -----------------------------------------------------
    # 6. RETURN RESULT
    # -----------------------------------------------------

    return validated