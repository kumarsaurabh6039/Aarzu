from pathlib import Path
from typing import List, Optional

from google import genai

from app.config import GEMINI_API_KEY, CHAT_MODEL
from app.rag.memory_search import search_memories
from app.rag.memory_extractor import extract_memory
from app.db.conversations import (
    get_or_create_conversation,
    log_message,
    get_recent_guest_summary,
)

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = Path(__file__).parent.parent / "prompts" / "aarzu_system.txt"
SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT.read_text(encoding="utf-8")


def _speaker_line(visitor_name: Optional[str], is_owner: bool) -> str:
    if is_owner:
        return "SPEAKER: Saurabh (the owner)"

    if visitor_name:
        return f"SPEAKER: {visitor_name} (a guest, not Saurabh)"

    return "SPEAKER: unknown - first message from this device/session"


def _to_gemini_history(history: List[dict]):
    formatted = []

    for turn in history:
        role = "user" if turn.get("role") == "user" else "model"
        content = turn.get("content", "")

        if content:
            formatted.append({
                "role": role,
                "parts": [{"text": content}],
            })

    return formatted


def chat_with_aarzu(
    user_id: str,
    message: str,
    visitor_name: Optional[str] = None,
    is_owner: bool = True,
    history: Optional[List[dict]] = None,
) -> str:

    history = history or []

    # Only pull owner's private long-term memories
    # when talking to Saurabh.
    if is_owner:

        memories = search_memories(
            user_id=user_id,
            query=message,
            limit=5
        ) or []

        memory_text = "\n".join(
            f"- {m['content']}"
            for m in memories
        ) or "(no relevant memories yet)"

        guest_summary = get_recent_guest_summary(
            user_id=user_id
        )

        extra_context = f"""PRIVATE MEMORIES ABOUT SAURABH:
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

    prompt = f"""{_speaker_line(visitor_name, is_owner)}

{extra_context}

CURRENT MESSAGE:
{message}
"""

    # Gemini new SDK
    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=[
            *(
                [
                    {
                        "role": item["role"],
                        "parts": item["parts"],
                    }
                    for item in _to_gemini_history(history)
                ]
            ),
            {
                "role": "user",
                "parts": [{"text": prompt}],
            },
        ],
        config={
            "system_instruction": SYSTEM_PROMPT_TEXT,
        },
    )

    reply_text = response.text

    # Log conversation
    # Never let logging failure break chat.
    try:

        conversation_id = get_or_create_conversation(
            user_id=user_id,
            speaker_name=visitor_name,
            is_owner=is_owner,
        )

        log_message(
            conversation_id,
            "user",
            message
        )

        log_message(
            conversation_id,
            "assistant",
            reply_text
        )

    except Exception:
        pass

    # Only extract long-term memories from Saurabh.
    if is_owner:

        try:
            extract_memory(
                user_id=user_id,
                message=message
            )

        except Exception:
            pass

    return reply_text