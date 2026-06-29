"""
LLM clients for the consumer-commission agent.

Two roles:
  - Groq Llama 3.3 70B  -> fast classification of issue type, quick rewrites
  - Gemini 2.5 Flash     -> long-form complaint drafting with structured output

Uses the new google-genai SDK (the old google-generativeai package is deprecated).
"""
from __future__ import annotations

import json
import time
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError as e:
    raise ImportError(
        "Could not import `google.genai`. The new Google Gen AI SDK package is "
        "`google-genai` (note the hyphen and the missing 'erative'). The OLD "
        "package `google-generativeai` is deprecated and does NOT provide "
        "`google.genai`.\n\n"
        "Fix:  pip install -U google-genai\n"
        "Then (optional, to silence the deprecation warning):  pip uninstall google-generativeai\n\n"
        f"Underlying error: {e}"
    ) from e
from groq import Groq

from . import config

_gemini = genai.Client(api_key=config.GOOGLE_API_KEY)
_groq = Groq(api_key=config.GROQ_API_KEY)


def _normalize_model(name: str | None, default: str) -> str:
    n = (name or default).strip()
    return n[len("models/") :] if n.startswith("models/") else n


def groq_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 600,
    response_format_json: bool = False,
) -> str:
    kwargs: dict[str, Any] = {
        "model": model or config.GROQ_FAST_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format_json:
        kwargs["response_format"] = {"type": "json_object"}
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = _groq.chat.completions.create(**kwargs)
            return r.choices[0].message.content or ""
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Groq call failed after retries: {last_err!r}")


def _build_gen_config(
    *,
    system_instruction: str | None,
    temperature: float,
    max_output_tokens: int,
    response_mime_type: str | None,
    response_schema: dict | None,
    thinking_budget: int | None,
) -> types.GenerateContentConfig:
    kwargs: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if response_mime_type:
        kwargs["response_mime_type"] = response_mime_type
    if response_schema:
        kwargs["response_schema"] = response_schema
    if thinking_budget is not None:
        # See legal-rag/core/llm.py for the rationale on disabling thinking by default.
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
    return types.GenerateContentConfig(**kwargs)


def gemini_generate(
    prompt: str,
    *,
    model: str | None = None,
    system_instruction: str | None = None,
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
    response_mime_type: str | None = None,
    response_schema: dict | None = None,
    thinking_budget: int | None = 0,
) -> str:
    cfg = _build_gen_config(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type=response_mime_type,
        response_schema=response_schema,
        thinking_budget=thinking_budget,
    )
    model_name = _normalize_model(model, config.GEMINI_DRAFT_MODEL)
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = _gemini.models.generate_content(
                model=model_name,
                contents=prompt,
                config=cfg,
            )
            return (r.text or "").strip()
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed after retries: {last_err!r}")


def gemini_json(prompt: str, schema: dict, **kwargs) -> dict:
    txt = gemini_generate(
        prompt, response_mime_type="application/json", response_schema=schema, **kwargs
    )
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned non-JSON: {txt[:200]!r}") from e
