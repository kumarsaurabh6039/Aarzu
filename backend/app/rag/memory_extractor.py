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


# ---------------------------------------------------------
# AI CLIENTS
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# MEMORY PROMPT
# ---------------------------------------------------------

MEMORY_PROMPT = """You are a personal memory extraction system.

Analyze the user's message and decide if it contains something worth
remembering about them long-term.

Good memories:
- goals
- career plans
- technical skills
- preferences
- important personal facts
- long-term plans
- important experiences
- recurring problems
- decisions

Do NOT store:
- random temporary statements
- passwords
- API keys
- card numbers
- unnecessary sensitive information

Return ONLY valid JSON.

If something is worth remembering, return:

{
  "should_save": true,
  "memory": "short useful memory",
  "memory_type": "goal",
  "importance": 8
}

If nothing is worth saving, return:

{
  "should_save": false
}

User message:
"""


# ---------------------------------------------------------
# JSON CLEANER
# ---------------------------------------------------------

def _parse_memory_response(text: str):

    if not text:
        return None

    text = text.strip()

    # Remove markdown code fences if model adds them
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
        return json.loads(text)

    except json.JSONDecodeError:

        print(
            "Memory extractor returned invalid JSON"
        )

        return None


# ---------------------------------------------------------
# GROQ MEMORY EXTRACTION
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# GEMINI MEMORY EXTRACTION FALLBACK
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# MAIN MEMORY EXTRACTION
# ---------------------------------------------------------

def extract_memory(
    user_id: str,
    message: str,
):

    data = None

    # -----------------------------------------------------
    # 1. GROQ PRIMARY
    # -----------------------------------------------------

    if groq_client:

        data = _extract_with_groq(message)

        if data:
            print("Memory extraction provider: Groq")


    # -----------------------------------------------------
    # 2. GEMINI FALLBACK
    # -----------------------------------------------------

    if data is None and gemini_client:

        data = _extract_with_gemini(message)

        if data:
            print("Memory extraction provider: Gemini")


    # -----------------------------------------------------
    # 3. BOTH PROVIDERS FAILED
    # -----------------------------------------------------

    if data is None:

        print(
            "Memory extraction failed on both providers"
        )

        return None


    # -----------------------------------------------------
    # 4. NOTHING WORTH SAVING
    # -----------------------------------------------------

    if not data.get("should_save"):

        return None


    # -----------------------------------------------------
    # 5. GET MEMORY
    # -----------------------------------------------------

    memory = data.get("memory")

    if not memory:

        return None


    # -----------------------------------------------------
    # 6. VALIDATE IMPORTANCE
    # -----------------------------------------------------

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
        min(10, importance)
    )


    # -----------------------------------------------------
    # 7. SAVE TO SUPABASE
    # -----------------------------------------------------

    save_memory(
        user_id=user_id,
        content=memory,
        memory_type=data.get(
            "memory_type",
            "general",
        ),
        importance=importance,
    )


    return data