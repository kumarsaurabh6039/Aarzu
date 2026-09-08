from fastapi import APIRouter
from pydantic import BaseModel

from app.config import DEFAULT_USER_ID
from app.db.supabase import supabase
from app.rag.memory_writer import save_memory

router = APIRouter()


class NewMemory(BaseModel):
    content: str
    memory_type: str = "general"
    importance: int = 5


@router.get("/memories")
def list_memories():
    result = (
        supabase.table("memories")
        .select("id, content, memory_type, importance, created_at")
        .eq("user_id", DEFAULT_USER_ID)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("/memories")
def add_memory(memory: NewMemory):
    return save_memory(
        user_id=DEFAULT_USER_ID,
        content=memory.content,
        memory_type=memory.memory_type,
        importance=memory.importance,
    )


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    supabase.table("memories").delete().eq("id", memory_id).execute()
    return {"deleted": memory_id}
