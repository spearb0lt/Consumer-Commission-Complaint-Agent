"""Env loading and project paths. Reads from project-local .env first, then parent /LegalTech/.env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = PROJECT_ROOT.parent

for candidate in (PROJECT_ROOT / ".env", PARENT_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)


def _require(name: str, *aliases: str) -> str:
    for key in (name, *aliases):
        v = os.environ.get(key)
        if v:
            return v
    raise RuntimeError(f"Missing env var. Set one of: {[name, *aliases]} in .env")


def _optional(name: str, *aliases: str, default: str | None = None) -> str | None:
    for key in (name, *aliases):
        v = os.environ.get(key)
        if v:
            return v
    return default


GOOGLE_API_KEY = _require("GOOGLE_API_KEY", "GEMINI_API_KEY")
GROQ_API_KEY = _require("GROQ_API_KEY")

GEMINI_DRAFT_MODEL = _optional("GEMINI_DRAFT_MODEL", default="gemini-2.5-flash")
GROQ_FAST_MODEL = _optional("GROQ_FAST_MODEL", default="llama-3.3-70b-versatile")

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
for d in (DATA_DIR, OUTPUT_DIR, TEMPLATE_DIR):
    d.mkdir(parents=True, exist_ok=True)
