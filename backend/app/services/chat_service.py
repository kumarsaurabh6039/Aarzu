from pathlib import Path
from typing import List, Optional

from groq import Groq
from google import genai

from app.config import (
    GROQ_API_KEY,
    GROQ_CHAT_MODEL,
    GEMINI_API_KEY,
    GEMINI_CHAT_MODEL,
)

from app.rag.memory_search import search_memories
from app.rag.memory_extractor import extract_memory

from app.db.conversations import (
    get_or_create_conversation,
    log_message,
    get_recent_guest_summary,
)


# ---------------------------------------------------------
# AI CLIENTS
# ---------------------------------------------------------

groq_client = None
gemini_client = None


if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)


if not groq_client and not gemini_client:
    raise RuntimeError(
        "Neither GROQ_API_KEY nor GEMINI_API_KEY is configured"
    )


# ---------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------

SYSTEM_PROMPT = (
    Path(__file__).parent.parent
    / "prompts"
    / "aarzu_system.txt"
)

SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT.read_text(
    encoding="utf-8"
)


# ---------------------------------------------------------
# SPEAKER
# ---------------------------------------------------------

def _speaker_line(
    visitor_name: Optional[str],
    is_owner: bool
) -> str:

    if is_owner:
        return "SPEAKER: Saurabh (the owner)"

    if visitor_name:
        return (
            f"SPEAKER: {visitor_name} "
            "(a guest, not Saurabh)"
        )

    return (
        "SPEAKER: unknown - "
        "first message from this device/session"
    )


# ---------------------------------------------------------
# GEMINI HISTORY
# ---------------------------------------------------------

def _to_gemini_history(history: List[dict]):

    formatted = []

    for turn in history:

        role = (
            "user"
            if turn.get("role") == "user"
            else "model"
        )

        content = turn.get("content", "")

        if content:

            formatted.append({
                "role": role,
                "parts": [
                    {
                        "text": content
                    }
                ],
            })

    return formatted


# ---------------------------------------------------------
# GROQ HISTORY
# ---------------------------------------------------------

def _to_groq_history(history: List[dict]):

    formatted = []

    for turn in history:

        role = turn.get("role")

        if role not in ("user", "assistant"):
            continue

        content = turn.get("content", "")

        if content:

            formatted.append({
                "role": role,
                "content": content,
            })

    return formatted


# ---------------------------------------------------------
# MAIN CHAT FUNCTION
# ---------------------------------------------------------

def chat_with_aarzu(
    user_id: str,
    message: str,
    visitor_name: Optional[str] = None,
    is_owner: bool = True,
    history: Optional[List[dict]] = None,
) -> str:

    # Keep only recent conversation history.
    # This prevents huge prompts as the conversation grows.
    history = (history or [])[-20:]

    # -----------------------------------------------------
    # MEMORY / RAG
    # -----------------------------------------------------

    if is_owner:

        try:

            memories = search_memories(
                user_id=user_id,
                query=message,
                limit=5,
            ) or []

        except Exception as e:

            print(
                f"Memory search error: {e}"
            )

            memories = []

        memory_text = "\n".join(
            f"- {m['content']}"
            for m in memories
        ) or "(no relevant memories yet)"

        try:

            guest_summary = get_recent_guest_summary(
                user_id=user_id
            )

        except Exception as e:

            print(
                f"Guest summary error: {e}"
            )

            guest_summary = "(no recent guest conversations)"

        extra_context = f"""
PRIVATE MEMORIES ABOUT SAURABH:
{memory_text}

RECENT CONVERSATIONS WITH OTHER PEOPLE:
(share naturally if Saurabh asks who talked to you
or what was said - don't volunteer this unprompted)

{guest_summary}
"""

    else:

        extra_context = (
            "(no memories shown - current speaker is a guest, "
            "not confirmed as Saurabh)"
        )

    # -----------------------------------------------------
    # CURRENT PROMPT
    # -----------------------------------------------------

    prompt = f"""
{_speaker_line(visitor_name, is_owner)}

{extra_context}

CURRENT MESSAGE:
{message}
"""

    # -----------------------------------------------------
    # GROQ PRIMARY
    # -----------------------------------------------------

    reply_text = None

    if groq_client:

        try:

            groq_messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT_TEXT,
                }
            ]

            groq_messages.extend(
                _to_groq_history(history)
            )

            groq_messages.append({
                "role": "user",
                "content": prompt,
            })

            response = groq_client.chat.completions.create(
                model=GROQ_CHAT_MODEL,
                messages=groq_messages,
                temperature=0.7,
            )

            reply_text = (
                response.choices[0]
                .message
                .content
            )

            print(
                f"Aarzu AI provider: Groq "
                f"({GROQ_CHAT_MODEL})"
            )

        except Exception as e:

            print(
                f"Groq technical error: {e}"
            )

    # -----------------------------------------------------
    # GEMINI FALLBACK
    # -----------------------------------------------------

    if not reply_text and gemini_client:

        try:

            gemini_contents = []

            gemini_contents.extend(
                _to_gemini_history(history)
            )

            gemini_contents.append({
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ],
            })

            response = (
                gemini_client.models.generate_content(
                    model=GEMINI_CHAT_MODEL,
                    contents=gemini_contents,
                    config={
                        "system_instruction":
                            SYSTEM_PROMPT_TEXT,
                    },
                )
            )

            reply_text = response.text

            print(
                f"Aarzu AI provider: Gemini "
                f"({GEMINI_CHAT_MODEL})"
            )

        except Exception as e:

            print(
                f"Gemini technical error: {e}"
            )

    # -----------------------------------------------------
    # BOTH AI PROVIDERS FAILED
    # -----------------------------------------------------

    if not reply_text:

        return (
            "Hey, something’s a little messed up "
            "on my side right now 😅 "
            "Can we talk a little later? "
            "I’ll be back soon."
        )

    # -----------------------------------------------------
    # LOG CONVERSATION
    # -----------------------------------------------------

    try:

        conversation_id = get_or_create_conversation(
            user_id=user_id,
            speaker_name=visitor_name,
            is_owner=is_owner,
        )

        log_message(
            conversation_id,
            "user",
            message,
        )

        log_message(
            conversation_id,
            "assistant",
            reply_text,
        )

    except Exception as e:

        print(
            f"Conversation logging error: {e}"
        )

    # -----------------------------------------------------
    # LONG-TERM MEMORY
    # -----------------------------------------------------

    if is_owner:

        try:

            extract_memory(
                user_id=user_id,
                message=message,
            )

        except Exception as e:

            print(
                f"Memory extraction error: {e}"
            )

    return reply_text