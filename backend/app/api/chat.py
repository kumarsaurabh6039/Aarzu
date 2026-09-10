from typing import List, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.config import DEFAULT_USER_ID, OWNER_ACCESS_KEY
from app.services.chat_service import chat_with_aarzu

router = APIRouter()


class HistoryTurn(BaseModel):
    role: str  # "user" or "assistant" (also accepts legacy "aarzu")
    content: str


class ChatRequest(BaseModel):
    message: str
    visitor_name: Optional[str] = None

    # Kept only for frontend backwards-compatibility. NEVER trusted on
    # its own - real owner status is decided from the header below.
    is_owner: bool = False

    history: List[HistoryTurn] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_aarzu_owner_key: Optional[str] = Header(default=None),
):
    # The only source of truth for "is this actually Saurabh" is a
    # server-known secret sent as a header. A guest sending
    # {"is_owner": true} in the JSON body gets no special access.
    is_owner = bool(OWNER_ACCESS_KEY) and x_aarzu_owner_key == OWNER_ACCESS_KEY

    answer = chat_with_aarzu(
        user_id=DEFAULT_USER_ID,
        message=request.message,
        visitor_name=request.visitor_name,
        is_owner=is_owner,
        history=[turn.model_dump() for turn in request.history],
    )
    return {"response": answer}
