from app.db.supabase import supabase
from app.services.embedding_service import create_embedding


def save_memory(
    user_id: str,
    content: str,
    memory_type: str = "general",
    importance: int = 5,
):
    embedding = create_embedding(content)

    result = (
        supabase.table("memories")
        .insert(
            {
                "user_id": user_id,
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
                "embedding": embedding,
            }
        )
        .execute()
    )

    return result.data
