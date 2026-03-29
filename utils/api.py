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
_CONNECT_TIMEOUT = 30.0


def _read_timeout_seconds(minimum_read: float) -> float:
    """Combine caller minimum with optional ``OPENROUTER_TIMEOUT`` (seconds to wait for response body)."""
    read = max(30.0, float(minimum_read))
    raw = (os.environ.get("OPENROUTER_TIMEOUT") or "").strip()
    if raw:
        try:
            read = max(read, float(raw))
        except ValueError:
            pass
    return read


def generate_text(
    prompt: str,
    *,
    model: str | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT,
    max_tokens: int | None = None,
) -> str:
    """Call OpenRouter chat completions and return assistant message text only.

    Reads ``OPENROUTER_API_KEY`` from the environment (optionally via a ``.env``
    file if ``python-dotenv`` is installed). Model defaults to
    ``OPENROUTER_MODEL`` or ``openai/gpt-4o-mini``.

    Args:
        prompt: User message content.
        model: OpenRouter model id; overrides ``OPENROUTER_MODEL`` when set.
        timeout_seconds: Minimum read timeout in seconds (connect is fixed shorter).
            Also set ``OPENROUTER_TIMEOUT`` in the environment to raise the read cap
            (useful for long diary generations).
        max_tokens: Optional cap on generated tokens (larger = longer replies).
            If omitted, uses provider default. Also set ``OPENROUTER_MAX_TOKENS``.

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
    token_cap = max_tokens
    if token_cap is None:
        raw_cap = (os.environ.get("OPENROUTER_MAX_TOKENS") or "").strip()
        if raw_cap.isdigit():
            token_cap = int(raw_cap)
    if token_cap is not None and token_cap > 0:
        body["max_tokens"] = int(token_cap)

    read_timeout = _read_timeout_seconds(timeout_seconds)
    timeouts = (_CONNECT_TIMEOUT, read_timeout)
    try:
        response = requests.post(
            _OPENROUTER_URL,
            headers=headers,
            json=body,
            timeout=timeouts,
        )
    except requests.exceptions.Timeout:
        print(
            f"[OpenRouter] timeout (connect {_CONNECT_TIMEOUT}s, read {read_timeout}s). "
            "Raise OPENROUTER_TIMEOUT in .env if generations are slow.",
        )
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

    # Legacy completion shape: text on the choice itself
    legacy = first.get("text")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()

    message = first.get("message")
    if not isinstance(message, dict):
        print("[OpenRouter] missing message in choice")
        return ""

    refusal = message.get("refusal")
    if refusal is not None and str(refusal).strip():
        print("[OpenRouter] model returned a refusal instead of normal content")
        return str(refusal).strip()

    content = message.get("content")

    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    chunks.append(str(part.get("text", "")))
                elif part.get("type") == "output_text" and part.get("text"):
                    chunks.append(str(part.get("text", "")))
            elif isinstance(part, str):
                chunks.append(part)
        out = "".join(chunks).strip()
        if out:
            return out
    elif isinstance(content, str) and content.strip():
        return content.strip()

    # Some reasoning models expose only reasoning fields when content is empty
    for key in ("reasoning", "reasoning_content", "reasoning_details"):
        alt = message.get(key)
        if alt is not None and str(alt).strip():
            print(f"[OpenRouter] using {key} as body (content was empty)")
            return str(alt).strip()

    print(
        "[OpenRouter] empty assistant message (check model id, credits, and "
        "whether the provider returned an unsupported shape)",
    )
    return ""
