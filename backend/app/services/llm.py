"""The only file that knows about Gemini. Returns plain text, nothing else."""
import os

from google import genai
from google.genai import types


def gemini_generate(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL")
    if not api_key or not model:
        raise RuntimeError("GEMINI_API_KEY and GEMINI_MODEL must be set")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30_000),  # milliseconds
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",  # ask for JSON, we still validate it
            temperature=0.2,
        ),
    )
    return response.text