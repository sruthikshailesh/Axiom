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


# Every LLM failure carries a message a non-developer can read in the UI. The
# raw provider detail stays in the exception text and in the backend log only.
MISSING_KEY_MESSAGE = (
    "The language model is not configured. Set LLM_API_KEY in backend/.env, "
    "then start the run again."
)
MISCONFIGURED_MESSAGE = (
    "The language model is not configured correctly. Check LLM_PROVIDER and "
    "LLM_MODEL in backend/.env, then start the run again."
)
BAD_KEY_MESSAGE = (
    "The language model rejected the API key. Check LLM_API_KEY in backend/.env, "
    "then start the run again."
)
RATE_LIMIT_MESSAGE = (
    "The language model is busy (rate limited). Wait a minute and start the run again."
)
TIMEOUT_MESSAGE = "The language model did not answer in time. Start the run again."
NETWORK_MESSAGE = (
    "Could not reach the language model service. Check the network, then start "
    "the run again."
)
UNAVAILABLE_MESSAGE = (
    "The language model service is unavailable right now. Start the run again."
)
BAD_RESPONSE_MESSAGE = (
    "The language model returned a response AXIOM could not use. Start the run again."
)
DEFAULT_PUBLIC_MESSAGE = "The language model call failed. Start the run again."


class LLMError(RuntimeError):
    """Raised when the provider is misconfigured or returns unusable JSON.

    ``str(error)`` is the raw detail for the backend log; ``public_message`` is
    the sentence shown to the user on the run.
    """

    def __init__(self, message: str, public_message: str = DEFAULT_PUBLIC_MESSAGE) -> None:
        super().__init__(message)
        self.public_message = public_message


def _config() -> Dict[str, str]:
    provider = (settings.llm_provider or "openai").strip().lower()
    api_key = (settings.llm_api_key or "").strip()
    model = (settings.llm_model or "").strip()
    base_url = (settings.llm_base_url or DEFAULT_BASE_URL).strip().rstrip("/")

    if not api_key:
        raise LLMError("LLM_API_KEY is not set", MISSING_KEY_MESSAGE)
    if provider not in SUPPORTED_PROVIDERS:
        raise LLMError(
            "Unsupported LLM_PROVIDER: {}. Supported providers: {}.".format(
                provider, ", ".join(SUPPORTED_PROVIDERS)
            ),
            MISCONFIGURED_MESSAGE,
        )
    if not model:
        raise LLMError("LLM_MODEL is not set", MISCONFIGURED_MESSAGE)

    return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}

def _public_message_for(status: int, body: str) -> str:
    """The user-facing sentence for one provider status code."""
    if status in (401, 403):
        return BAD_KEY_MESSAGE
    if status == 429:
        return RATE_LIMIT_MESSAGE
    if status >= 500:
        return UNAVAILABLE_MESSAGE
    if status == 400 and JSON_VALIDATION_ERROR in body:
        return BAD_RESPONSE_MESSAGE
    return DEFAULT_PUBLIC_MESSAGE


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
        except httpx.TimeoutException as exc:
            response = None
            error = LLMError("LLM request timed out: {}".format(exc), TIMEOUT_MESSAGE)
        except httpx.HTTPError as exc:
            response = None
            error = LLMError("LLM request failed: {}".format(exc), NETWORK_MESSAGE)
        else:
            if response.status_code < 400:
                break
            body = response.text
            error = LLMError(
                "LLM provider returned HTTP {}: {}".format(response.status_code, body[:300]),
                _public_message_for(response.status_code, body),
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
        raise LLMError(
            "LLM provider returned an unexpected response shape.", BAD_RESPONSE_MESSAGE
        )


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
            "LLM did not return valid JSON after one retry: {}".format(exc),
            BAD_RESPONSE_MESSAGE,
        )
