import os
from google import genai

from app.config import GEMINI_API_KEY, EMBEDDING_MODEL


if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")


client = genai.Client(api_key=GEMINI_API_KEY)


def create_embedding(text: str) -> list[float]:
    """Create a 768-dimensional embedding using Gemini."""

    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "output_dimensionality": 768
        }
    )

    return result.embeddings[0].values