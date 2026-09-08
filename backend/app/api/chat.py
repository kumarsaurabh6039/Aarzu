from fastapi import APIRouter
from pydantic import BaseModel

from app.config import DEFAULT_USER_ID
from app.services.chat_service import chat_with_aarzu

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer = chat_with_aarzu(user_id=DEFAULT_USER_ID, message=request.message)
    return {"response": answer}
