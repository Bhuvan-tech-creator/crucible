"""
core/groq_client.py
Thin wrapper around the Groq Python SDK.
Provides a stateful client that can be configured at runtime (via the /api/set-key
endpoint) so the user never has to restart the server after changing the key.
"""

import os
from groq import Groq

# Module-level client instance — updated by set_api_key()
_client: Groq | None = None
_api_key: str = os.environ.get("GROQ_API_KEY", "").strip()

# Default model tiers
FAST_MODEL = "llama-3.1-8b-instant"     # Used for per-agent debate turns (high throughput)
SMART_MODEL = "llama-3.3-70b-versatile"  # Used for document analysis and judge verdict


def set_api_key(key: str) -> None:
    """Replace the active Groq API key and reset the client."""
    global _client, _api_key
    _api_key = key.strip()
    _client = None  # Force re-initialisation on next call


def get_client() -> Groq:
    """Return a live Groq client, creating one if needed."""
    global _client
    if not _api_key:
        raise RuntimeError(
            "No Groq API key configured. "
            "Set GROQ_API_KEY in your .env file or enter it in the UI."
        )
    if _client is None:
        _client = Groq(api_key=_api_key)
    return _client


def chat(
    messages: list[dict],
    model: str = FAST_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    Send a chat completion request and return the assistant's reply text.

    Args:
        messages:     List of {"role": ..., "content": ...} dicts.
        model:        Groq model ID.
        temperature:  Sampling temperature (0.0–1.0).
        max_tokens:   Maximum tokens in the completion.

    Returns:
        The assistant's reply as a plain string.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content