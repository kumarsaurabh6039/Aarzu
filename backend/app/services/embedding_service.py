import google.generativeai as genai
from app.config import GEMINI_API_KEY, EMBEDDING_MODEL

genai.configure(api_key=GEMINI_API_KEY)


def create_embedding(text: str) -> list[float]:
    """Turn text into a 768-dim vector using Gemini's free embedding model."""
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_document",
        output_dimensionality=768,
    )
    return result["embedding"]