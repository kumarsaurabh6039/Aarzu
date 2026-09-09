from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import DEFAULT_USER_ID
from app.services.chat_service import chat_with_aarzu

router = APIRouter()


class HistoryTurn(BaseModel):
    role: str  # "user" or "aarzu"
    content: str


class ChatRequest(BaseModel):
    message: str
    visitor_name: Optional[str] = None
    is_owner: bool = True
    history: List[HistoryTurn] = []


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer = chat_with_aarzu(
        user_id=DEFAULT_USER_ID,
        message=request.message,
        visitor_name=request.visitor_name,
        is_owner=request.is_owner,
        history=[turn.model_dump() for turn in request.history],
    )
    return {"response": answer}
