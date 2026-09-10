from datetime import datetime, timezone
from typing import Optional

from app.db.supabase import supabase
from app.services.embedding_service import create_embedding

# We keep ONE open conversation per "identity" (owner, or a given guest
# name, or a single bucket for unnamed guests) so a whole chat thread
# stays grouped together instead of creating a new row per message.


def get_or_create_conversation(user_id: str, speaker_name: Optional[str], is_owner: bool) -> str:
    title = "Saurabh" if is_owner else (speaker_name or "Unknown guest")

    existing = (
        supabase.table("conversations")
        .select("id")
        .eq("user_id", user_id)
        .eq("is_owner", is_owner)
        .eq("title", title)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    created = (
        supabase.table("conversations")
        .insert(
            {
                "user_id": user_id,
                "title": title,
                "speaker_name": speaker_name,
                "is_owner": is_owner,
            }
        )
        .execute()
    )
    return created.data[0]["id"]


def log_message(conversation_id: str, role: str, content: str, is_owner: bool = True) -> None:
    """Save a message.

    Only a GUEST's own messages (role == "user" and is_owner == False) get
    an embedding, since that's the only thing search_guest_messages() ever
    needs to find later. This keeps Saurabh's own messages and every
    assistant reply out of the guest-search vector index, and avoids
    burning embedding calls where they'd never be used.
    """
    payload = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }

    if role == "user" and not is_owner:
        try:
            payload["embedding"] = create_embedding(content)
        except Exception as e:
            # A failed embedding should never stop the message from
            # being saved - it just won't be semantically searchable.
            print(f"Guest message embedding error: {e}")

    supabase.table("messages").insert(payload).execute()

    supabase.table("conversations").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).execute()


def get_recent_guest_summary(user_id: str, max_conversations: int = 3, max_messages_each: int = 6) -> str:
    """A short digest of recent non-owner conversations, for Saurabh's context.

    Only meant to be shown to Saurabh himself - never to another guest.
    """
    convos = (
        supabase.table("conversations")
        .select("id, title, updated_at")
        .eq("user_id", user_id)
        .eq("is_owner", False)
        .order("updated_at", desc=True)
        .limit(max_conversations)
        .execute()
    )
    if not convos.data:
        return "(no one else has talked to Aarzu recently)"

    chunks = []
    for convo in convos.data:
        msgs = (
            supabase.table("messages")
            .select("role, content")
            .eq("conversation_id", convo["id"])
            .order("created_at", desc=True)
            .limit(max_messages_each)
            .execute()
        )
        lines = [f"  {m['role']}: {m['content']}" for m in reversed(msgs.data or [])]
        chunks.append(f"- Conversation with {convo['title']}:\n" + "\n".join(lines))

    return "\n".join(chunks)
