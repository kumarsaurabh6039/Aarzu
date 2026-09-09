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


if not groq_client and not gemini_client:
    raise RuntimeError(
        "Neither GROQ_API_KEY nor GEMINI_API_KEY is configured"
    )


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT_PATH = (
    Path(__file__).parent.parent
    / "prompts"
    / "aarzu_system.txt"
)

SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT_PATH.read_text(
    encoding="utf-8"
)


# =========================================================
# MEMORY GATE
# =========================================================

# These phrases indicate that the user may be sharing
# something useful for long-term memory.

MEMORY_KEYWORDS = [
    # Explicit memory requests
    "remember",
    "don't forget",
    "do not forget",
    "save this",
    "keep this in mind",

    # Goals / plans
    "my goal",
    "my goals",
    "my plan",
    "my plans",
    "i want to",
    "i want",
    "i plan to",
    "i'm planning",
    "i am planning",
    "i decided",
    "i have decided",

    # Learning / career
    "i am learning",
    "i'm learning",
    "i am studying",
    "i'm studying",
    "i work",
    "i worked",
    "my career",
    "career goal",
    "career plan",

    # Projects
    "my project",
    "my projects",
    "i built",
    "i am building",
    "i'm building",
    "i created",
    "i am working on",
    "i'm working on",

    # Preferences
    "my preference",
    "my preferences",
    "i prefer",
    "i like",
    "i love",
    "i don't like",
    "i dislike",

    # Future / long-term
    "in future",
    "in the future",
    "from now",
    "going forward",
    "long term",
    "long-term",

    # Useful personal context
    "my name is",
    "i live in",
    "i am from",
    "i'm from",
]


def _should_check_memory(message: str) -> bool:
    """
    Cheap local filter.

    Prevents a second AI request for ordinary messages.
    """

    text = message.lower().strip()

    if not text:
        return False

    return any(
        keyword in text
        for keyword in MEMORY_KEYWORDS
    )


# =========================================================
# SPEAKER
# =========================================================

def _speaker_line(
    visitor_name: Optional[str],
    is_owner: bool,
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


# =========================================================
# GEMINI HISTORY
# =========================================================

def _to_gemini_history(
    history: List[dict],
) -> List[dict]:

    formatted = []

    for turn in history:

        role = turn.get("role")

        if role == "user":
            gemini_role = "user"

        elif role == "assistant":
            gemini_role = "model"

        else:
            continue

        content = turn.get("content", "")

        if not content:
            continue

        formatted.append({
            "role": gemini_role,
            "parts": [
                {
                    "text": content
                }
            ],
        })

    return formatted


# =========================================================
# GROQ HISTORY
# =========================================================

def _to_groq_history(
    history: List[dict],
) -> List[dict]:

    formatted = []

    for turn in history:

        role = turn.get("role")

        if role not in (
            "user",
            "assistant",
        ):
            continue

        content = turn.get("content", "")

        if not content:
            continue

        formatted.append({
            "role": role,
            "content": content,
        })

    return formatted


# =========================================================
# PRIVATE MEMORY / RAG
# =========================================================

def _get_owner_context(
    user_id: str,
    message: str,
) -> str:

    # -----------------------------------------------------
    # Search long-term memories
    # -----------------------------------------------------

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
        f"- {memory.get('content', '')}"
        for memory in memories
        if memory.get("content")
    )

    if not memory_text:
        memory_text = "(no relevant memories yet)"


    # -----------------------------------------------------
    # Recent guest conversation summary
    # -----------------------------------------------------

    try:

        guest_summary = get_recent_guest_summary(
            user_id=user_id
        )

    except Exception as e:

        print(
            f"Guest summary error: {e}"
        )

        guest_summary = (
            "(no recent guest conversations)"
        )


    return f"""
PRIVATE MEMORIES ABOUT SAURABH:
{memory_text}

RECENT CONVERSATIONS WITH OTHER PEOPLE:
(Share this naturally only if Saurabh asks about
who talked to you or what was discussed.
Do not volunteer this information unnecessarily.)

{guest_summary}
"""


# =========================================================
# CURRENT PROMPT
# =========================================================

def _build_prompt(
    user_id: str,
    message: str,
    visitor_name: Optional[str],
    is_owner: bool,
) -> str:

    if is_owner:

        extra_context = _get_owner_context(
            user_id=user_id,
            message=message,
        )

    else:

        extra_context = (
            "(no private memories are available. "
            "The current speaker is a guest and is "
            "not confirmed as Saurabh.)"
        )


    return f"""
{_speaker_line(visitor_name, is_owner)}

{extra_context}

CURRENT MESSAGE:
{message}
"""


# =========================================================
# GROQ CHAT
# =========================================================

def _chat_with_groq(
    prompt: str,
    history: List[dict],
) -> Optional[str]:

    if not groq_client:
        return None


    try:

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_TEXT,
            }
        ]


        messages.extend(
            _to_groq_history(history)
        )


        messages.append({
            "role": "user",
            "content": prompt,
        })


        response = groq_client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=messages,
            temperature=0.7,
        )


        reply = (
            response.choices[0]
            .message
            .content
        )


        if not reply:
            return None


        print(
            f"Aarzu AI provider: Groq "
            f"({GROQ_CHAT_MODEL})"
        )


        return reply.strip()


    except Exception as e:

        print(
            f"Groq technical error: {e}"
        )

        return None


# =========================================================
# GEMINI CHAT
# =========================================================

def _chat_with_gemini(
    prompt: str,
    history: List[dict],
) -> Optional[str]:

    if not gemini_client:
        return None


    try:

        contents = []

        contents.extend(
            _to_gemini_history(history)
        )


        contents.append({
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
                contents=contents,
                config={
                    "system_instruction":
                        SYSTEM_PROMPT_TEXT,
                },
            )
        )


        reply = response.text


        if not reply:
            return None


        print(
            f"Aarzu AI provider: Gemini "
            f"({GEMINI_CHAT_MODEL})"
        )


        return reply.strip()


    except Exception as e:

        print(
            f"Gemini technical error: {e}"
        )

        return None


# =========================================================
# CONVERSATION LOGGING
# =========================================================

def _save_conversation(
    user_id: str,
    message: str,
    reply_text: str,
    visitor_name: Optional[str],
    is_owner: bool,
) -> None:

    try:

        conversation_id = (
            get_or_create_conversation(
                user_id=user_id,
                speaker_name=visitor_name,
                is_owner=is_owner,
            )
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

        # Database failure should NOT destroy
        # an otherwise successful AI response.

        print(
            f"Conversation logging error: {e}"
        )


# =========================================================
# LONG-TERM MEMORY
# =========================================================

def _maybe_save_memory(
    user_id: str,
    message: str,
    is_owner: bool,
) -> None:

    if not is_owner:
        return


    # -----------------------------------------------------
    # Cheap local check.
    #
    # Most normal messages will stop here and won't
    # consume another Groq request.
    # -----------------------------------------------------

    if not _should_check_memory(message):

        print(
            "Memory extraction skipped "
            "(message does not look memory-worthy)"
        )

        return


    try:

        result = extract_memory(
            user_id=user_id,
            message=message,
        )


        if result:

            print(
                "Long-term memory processed"
            )

        else:

            print(
                "Memory check completed - "
                "nothing saved"
            )


    except Exception as e:

        # Memory failure should NEVER break chat.

        print(
            f"Memory extraction error: {e}"
        )


# =========================================================
# MAIN CHAT FUNCTION
# =========================================================

def chat_with_aarzu(
    user_id: str,
    message: str,
    visitor_name: Optional[str] = None,
    is_owner: bool = True,
    history: Optional[List[dict]] = None,
) -> str:

    # -----------------------------------------------------
    # Sanitize input
    # -----------------------------------------------------

    message = (message or "").strip()

    if not message:

        return (
            "I didn't catch that 😅"
        )


    # -----------------------------------------------------
    # Keep only recent conversation history.
    # -----------------------------------------------------

    history = (
        (history or [])[-20:]
    )


    # -----------------------------------------------------
    # Build complete prompt
    # -----------------------------------------------------

    prompt = _build_prompt(
        user_id=user_id,
        message=message,
        visitor_name=visitor_name,
        is_owner=is_owner,
    )


    # -----------------------------------------------------
    # 1. GROQ PRIMARY
    # -----------------------------------------------------

    reply_text = _chat_with_groq(
        prompt=prompt,
        history=history,
    )


    # -----------------------------------------------------
    # 2. GEMINI FALLBACK
    # -----------------------------------------------------

    if not reply_text:

        print(
            "Groq unavailable. "
            "Trying Gemini fallback..."
        )

        reply_text = _chat_with_gemini(
            prompt=prompt,
            history=history,
        )


    # -----------------------------------------------------
    # 3. BOTH PROVIDERS FAILED
    # -----------------------------------------------------

    if not reply_text:

        return (
            "Hey, something’s a little messed up "
            "on my side right now 😅 "
            "Can we talk a little later? "
            "I’ll be back soon."
        )


    # -----------------------------------------------------
    # 4. SAVE CONVERSATION
    # -----------------------------------------------------

    _save_conversation(
        user_id=user_id,
        message=message,
        reply_text=reply_text,
        visitor_name=visitor_name,
        is_owner=is_owner,
    )


    # -----------------------------------------------------
    # 5. SMART LONG-TERM MEMORY
    # -----------------------------------------------------

    _maybe_save_memory(
        user_id=user_id,
        message=message,
        is_owner=is_owner,
    )


    # -----------------------------------------------------
    # Return response
    # -----------------------------------------------------

    return reply_text