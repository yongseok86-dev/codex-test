from __future__ import annotations

from typing import Optional
from app.services import prompt as prompt_builder
from app.semantic.loader import load_semantic_root
from app.config import settings
from app.deps import get_logger

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


class LLMNotConfigured(Exception):
    pass


def generate_sql_via_llm(question: str, provider: Optional[str] = None) -> str:
    semantic = load_semantic_root()
    prompt = prompt_builder.build_sql_prompt(question, semantic)

    provider = (provider or settings.llm_provider or "").lower()
    system_prompt = settings.llm_system_prompt or "Generate ONLY SQL in BigQuery dialect in a code fence."
    temperature = float(getattr(settings, "llm_temperature", 0.1))
    max_tokens = int(getattr(settings, "llm_max_tokens", 1024))
    logger = get_logger(__name__)
    if provider == "openai":
        if OpenAI is None or not settings.openai_api_key:
            raise LLMNotConfigured("OpenAI provider not available or missing API key")
        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model or "gpt-4o-mini"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        return _extract_sql_from_text(content)

    if provider in {"claude", "anthropic"}:
        if anthropic is None or not settings.anthropic_api_key:
            raise LLMNotConfigured("Anthropic provider not available or missing API key")
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = settings.anthropic_model or "claude-3-5-sonnet-20240620"
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        # content is a list of content blocks; take text
        text_parts = []
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", "") == "text":
                text_parts.append(getattr(block, "text", ""))
        content = "\n".join(text_parts) or str(resp)
        return _extract_sql_from_text(content)

    if provider in {"gemini", "google", "gcp"}:
        if genai is None or not settings.gemini_api_key:
            raise LLMNotConfigured("Gemini provider not available or missing API key")
        genai.configure(api_key=settings.gemini_api_key)
        model = settings.gemini_model or "gemini-1.5-flash"
        m = genai.GenerativeModel(model)
        resp = m.generate_content(prompt, generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        })
        content = getattr(resp, "text", None) or "\n".join(getattr(resp, "candidates", []) or [])
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
