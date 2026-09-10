from app.db.supabase import supabase
from app.services.embedding_service import create_embedding


def search_memories(user_id: str, query: str, limit: int = 5):
    """Semantic search over Saurabh's private long-term memories only."""
    query_embedding = create_embedding(query)

    result = supabase.rpc(
        "match_memories",
        {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_threshold": 0.65,
            "match_count": limit,
        },
    ).execute()

    return result.data


def search_guest_messages(user_id: str, query: str, limit: int = 8):
    """Semantic search over what guests (never the owner) have said.

    Threshold is intentionally lower than search_memories() because guest
    messages tend to be short and conversational rather than distilled
    long-term facts.
    """
    query_embedding = create_embedding(query)

    result = supabase.rpc(
        "match_guest_messages",
        {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_threshold": 0.55,
            "match_count": limit,
        },
    ).execute()

    return result.data
