from __future__ import annotations

from typing import Optional
from app.services import prompt as prompt_builder
from app.semantic.loader import load_semantic_root
from app.config import settings

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


class LLMNotConfigured(Exception):
    pass


def generate_sql_via_llm(question: str) -> str:
    semantic = load_semantic_root()
    prompt = prompt_builder.build_sql_prompt(question, semantic)

    provider = (settings.llm_provider or "").lower()
    if provider == "openai":
        if OpenAI is None or not settings.openai_api_key:
            raise LLMNotConfigured("OpenAI provider not available or missing API key")
        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model or "gpt-4o-mini"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You generate only SQL in code fences."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = resp.choices[0].message.content or ""
        return _extract_sql_from_text(content)

    # More providers can be added here (Vertex AI, Azure OpenAI)
    raise LLMNotConfigured("No LLM provider configured")


def _extract_sql_from_text(text: str) -> str:
    start = text.find("```sql")
    if start == -1:
        return text.strip()
    start += len("```sql")
    end = text.find("```", start)
    if end == -1:
        end = len(text)
    return text[start:end].strip()

