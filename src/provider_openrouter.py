# src/provider_openrouter.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
import logging

import requests

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openrouter/horizon-beta"
OPENROUTER_API_KEY_FILE_PATH = Path.home() / ".api-openrouter"


def _resolve_openrouter_api_key() -> Optional[str]:
    env_key = os.getenv("OPENROUTER_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    try:
        if OPENROUTER_API_KEY_FILE_PATH.is_file():
            return OPENROUTER_API_KEY_FILE_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


def _to_messages(prompt: str) -> list[dict]:
    return [{"role": "user", "content": prompt}]


def generate_with_openrouter(
    prompt: str,
    model_name: str = DEFAULT_OPENROUTER_MODEL,
    max_new_tokens: int = 150,
    timeout: int = 60,
) -> Optional[str]:
    """
    Call OpenRouter Chat Completions to generate text.
    Returns the content string on success, or None on failure.
    """
    api_key = _resolve_openrouter_api_key()
    if not api_key:
        logging.error("OpenRouter API key missing: set OPENROUTER_API_KEY or ~/.api-openrouter")
        return None

    payload = {
        "model": model_name or DEFAULT_OPENROUTER_MODEL,
        "messages": _to_messages(prompt),
        "temperature": 0.2,
        "max_tokens": max_new_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            logging.error(f"OpenRouter non-200: {resp.status_code} {resp.text[:500]}")
            return None
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return None
        content = (choices[0].get("message", {}).get("content") or "").strip()
        return content or None
    except Exception as e:
        logging.error(f"OpenRouter call failed: {e}")
        return None