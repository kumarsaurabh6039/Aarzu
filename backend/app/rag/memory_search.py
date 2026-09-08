from app.db.supabase import supabase
from app.services.embedding_service import create_embedding


def search_memories(user_id: str, query: str, limit: int = 5):
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
