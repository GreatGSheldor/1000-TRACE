

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

MODEL_NAME = "gemini-3.6-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT = 45
MAX_OUTPUT_TOKENS = 4096

BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / "gemini_key.txt"

BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / "gemini_key.txt"


class GeminiError(Exception):
    """Base class for every error this module raises."""


class GeminiConfigError(GeminiError):
    """Raised when no API key is configured."""


class GeminiNetworkError(GeminiError):
    """Raised on connection problems / timeouts."""


class GeminiAPIError(GeminiError):
    """Raised when Gemini responds with a non-2xx status or an odd body."""


def get_api_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key

    if KEY_FILE.exists():
        try:
            key = KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            key = ""
        if key:
            return key

    return None


def is_configured() -> bool:
    return get_api_key() is not None


def generate(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.3,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Send ``prompt`` to Gemini 2.5 Flash and return the plain-text reply.

    Raises GeminiConfigError / GeminiNetworkError / GeminiAPIError on
    failure - callers (the UI layer) are expected to catch ``GeminiError``
    and show a readable message rather than letting the app crash.
    """

    api_key = get_api_key()
    if not api_key:
        raise GeminiConfigError(
            "No Gemini API key configured. Set the GEMINI_API_KEY "
            "environment variable, or create a 'gemini_key.txt' file in "
            "the project root containing just the key."
        )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    url = f"{API_BASE}/{MODEL_NAME}:generateContent?key={api_key}"

    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            body = json.load(response)
    except urlerror.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        if exc.code in (401, 403):
            raise GeminiConfigError(
                "Gemini rejected the API key (unauthorized). Double check "
                "GEMINI_API_KEY."
            ) from exc
        if exc.code == 429:
            raise GeminiAPIError(
                "Gemini rate limit hit. Please wait a moment and try again."
            ) from exc
        raise GeminiAPIError(f"Gemini API error {exc.code}: {detail[:300]}") from exc
    except urlerror.URLError as exc:
        raise GeminiNetworkError(
            f"Could not reach Gemini API (network issue): {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise GeminiNetworkError("Gemini API request timed out.") from exc
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as-is
        raise GeminiAPIError(f"Unexpected Gemini client error: {exc}") from exc

    return _extract_text(body)


def _extract_text(body: dict) -> str:
    try:
        candidates = body.get("candidates") or []
        if not candidates:
            feedback = body.get("promptFeedback", {})
            reason = feedback.get("blockReason")
            if reason:
                raise GeminiAPIError(f"Gemini blocked this request ({reason}).")
            raise GeminiAPIError("Gemini returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()

        if not text:
            finish_reason = candidates[0].get("finishReason", "UNKNOWN")
            raise GeminiAPIError(f"Gemini returned an empty reply ({finish_reason}).")

        return text
    except GeminiAPIError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GeminiAPIError(f"Could not parse Gemini response: {exc}") from exc
