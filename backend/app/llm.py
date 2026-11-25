"""LLM adapter: one function, complete_json, over an OpenAI-compatible provider.

Configuration is read from the environment at call time, so a missing key is a
per-request error rather than an import-time crash:

    LLM_PROVIDER  provider name (only "openai" is implemented)
    LLM_API_KEY   bearer token; never committed
    LLM_MODEL     model name
    LLM_BASE_URL  optional; defaults to https://api.openai.com/v1
"""

from app.config import settings

import json
import time
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
SUPPORTED_PROVIDERS = ("openai",)
TIMEOUT_SECONDS = 60.0

# The configured model intermittently drops a connection, hits the rate limit, or
# has its JSON rejected by the provider's validator. Those are retried a few times
# with a short backoff (NOTES, Phase 5b); everything else fails immediately.
MAX_ATTEMPTS = 4
RETRY_DELAY_SECONDS = 2.0
RETRY_STATUSES = (429, 500, 502, 503, 504)
JSON_VALIDATION_ERROR = "json_validate_failed"


class LLMError(RuntimeError):
    """Raised when the provider is misconfigured or returns unusable JSON."""

def _config() -> Dict[str, str]:
    provider = (settings.llm_provider or "openai").strip().lower()
    api_key = (settings.llm_api_key or "").strip()
    model = (settings.llm_model or "").strip()
    base_url = (settings.llm_base_url or DEFAULT_BASE_URL).strip().rstrip("/")

    if not api_key:
        raise LLMError("LLM_API_KEY is not set")
    if provider not in SUPPORTED_PROVIDERS:
        raise LLMError(
            "Unsupported LLM_PROVIDER: {}. Supported providers: {}.".format(
                provider, ", ".join(SUPPORTED_PROVIDERS)
            )
        )
    if not model:
        raise LLMError("LLM_MODEL is not set")

    return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}

def _chat(config: Dict[str, str], messages: List[Dict[str, str]]) -> str:
    """One provider call, returning the raw assistant text."""
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": "Bearer " + config["api_key"]}

    response: Optional[httpx.Response] = None
    error: Optional[LLMError] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                response = client.post(
                    config["base_url"] + "/chat/completions", json=payload, headers=headers
                )
        except httpx.HTTPError as exc:
            response = None
            error = LLMError("LLM request failed: {}".format(exc))
        else:
            if response.status_code < 400:
                break
            body = response.text
            error = LLMError(
                "LLM provider returned HTTP {}: {}".format(response.status_code, body[:300])
            )
            retryable = response.status_code in RETRY_STATUSES or (
                response.status_code == 400 and JSON_VALIDATION_ERROR in body
            )
            if not retryable:
                raise error

        if attempt == MAX_ATTEMPTS - 1:
            raise error or LLMError("LLM request failed")
        time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

    if response is None:
        raise error or LLMError("LLM request failed")

    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise LLMError("LLM provider returned an unexpected response shape.")


def _extract_json(raw: str) -> Dict[str, Any]:
    """Parse a JSON object, tolerating ``` fences around it."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("response contains no JSON object")
        try:
            parsed = json.loads(text[start : end + 1])
        except ValueError as exc:
            raise ValueError(str(exc))

    if not isinstance(parsed, dict):
        raise ValueError("response JSON is not an object")
    return parsed


def complete_json(system: str, user: str, schema_hint: str) -> Dict[str, Any]:
    """Ask the provider for one JSON object; retry once on invalid JSON."""
    config = _config()
    messages = [
        {
            "role": "system",
            "content": "{}\n\nRespond with a single JSON object and nothing else, "
            "matching this shape:\n{}".format(system, schema_hint),
        },
        {"role": "user", "content": user},
    ]

    raw = _chat(config, messages)
    try:
        return _extract_json(raw)
    except ValueError as exc:
        problem = str(exc)

    retry_messages = messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": "That was not valid JSON ({}). Reply with the corrected JSON "
            "object only.".format(problem),
        },
    ]
    raw_retry = _chat(config, retry_messages)
    try:
        return _extract_json(raw_retry)
    except ValueError as exc:
        raise LLMError(
            "LLM did not return valid JSON after one retry: {}".format(exc)
        )
