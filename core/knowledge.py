"""Loads and serves the static knowledge base (CPA sections, jurisdiction rules, playbook)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from . import config


@lru_cache(maxsize=1)
def cpa_sections() -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "cpa_sections.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def jurisdictions() -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "jurisdictions.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def playbook() -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "playbook.json").read_text(encoding="utf-8"))


def category_keys() -> list[str]:
    return [c["key"] for c in playbook()["categories"]]


def category_labels() -> list[tuple[str, str]]:
    return [(c["key"], c["label"]) for c in playbook()["categories"]]


def category(key: str) -> dict[str, Any]:
    for c in playbook()["categories"]:
        if c["key"] == key:
            return c
    raise KeyError(f"Unknown complaint category key: {key}")


def section_by_id(sec_id: str) -> dict[str, Any] | None:
    for s in cpa_sections()["sections"]:
        if s["section"] == sec_id:
            return s
    return None
