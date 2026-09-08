from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.api.chat import router as chat_router
from app.api.memories import router as memories_router

app = FastAPI(title="Aarzu API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(memories_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Aarzu API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
