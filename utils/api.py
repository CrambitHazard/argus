"""HTTP helpers for external APIs (OpenRouter text generation)."""

import json
import os
from typing import Any

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "openai/gpt-4o-mini"
_DEFAULT_TIMEOUT = 60.0


def generate_text(
    prompt: str,
    *,
    model: str | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT,
) -> str:
    """Call OpenRouter chat completions and return assistant message text only.

    Reads ``OPENROUTER_API_KEY`` from the environment (optionally via a ``.env``
    file if ``python-dotenv`` is installed). Model defaults to
    ``OPENROUTER_MODEL`` or ``openai/gpt-4o-mini``.

    Args:
        prompt: User message content.
        model: OpenRouter model id; overrides ``OPENROUTER_MODEL`` when set.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Trimmed assistant text, or empty string on failure (after a short
        stderr-style debug line).

    Raises:
        Nothing; errors are swallowed into ``""`` with minimal logging.
    """
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        print("[OpenRouter] missing OPENROUTER_API_KEY")
        return ""

    resolved_model = (model or os.environ.get("OPENROUTER_MODEL") or _DEFAULT_MODEL).strip()
    if not resolved_model:
        print("[OpenRouter] no model configured")
        return ""

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    referer = (os.environ.get("OPENROUTER_HTTP_REFERER") or "").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    title = (os.environ.get("OPENROUTER_APP_TITLE") or "Argus").strip()
    if title:
        headers["X-Title"] = title

    body: dict[str, Any] = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(
            _OPENROUTER_URL,
            headers=headers,
            json=body,
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout:
        print(f"[OpenRouter] timeout after {timeout_seconds}s")
        return ""
    except requests.exceptions.RequestException as exc:
        print(f"[OpenRouter] request failed: {exc}")
        return ""

    try:
        data = response.json()
    except json.JSONDecodeError:
        print(f"[OpenRouter] invalid JSON (HTTP {response.status_code})")
        return ""

    if response.status_code != 200:
        err = data.get("error") if isinstance(data, dict) else data
        print(f"[OpenRouter] HTTP {response.status_code}: {err}")
        return ""

    if not isinstance(data, dict):
        print("[OpenRouter] unexpected response shape")
        return ""

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        print("[OpenRouter] no choices in response")
        return ""

    first = choices[0]
    if not isinstance(first, dict):
        return ""

    message = first.get("message")
    if not isinstance(message, dict):
        print("[OpenRouter] missing message in choice")
        return ""

    content = message.get("content")
    if content is None:
        return ""

    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                chunks.append(str(part.get("text", "")))
            elif isinstance(part, str):
                chunks.append(part)
        return "".join(chunks).strip()

    return str(content).strip()
