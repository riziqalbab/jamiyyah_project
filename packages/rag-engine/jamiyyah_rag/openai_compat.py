"""Dependency-free OpenAI-compatible HTTP client for Embeddings and Chat Completions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any


class OpenAICompatError(RuntimeError):
    """Raised when an OpenAI-compatible endpoint fails or returns invalid data."""


TransportFn = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


def _default_post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OpenAICompatError(f"HTTP {exc.code} from {url}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise OpenAICompatError(f"Connection failed to {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OpenAICompatError(f"Invalid JSON response from {url}") from exc


class OpenAICompatClient:
    """Minimal client targeting OpenAI-compatible ``/embeddings`` and ``/chat/completions``."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 30.0,
        transport: TransportFn | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._transport = transport or _default_post_json

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        """Request dense vector embeddings for ``texts`` via ``POST /embeddings``."""
        if not texts:
            return []
        url = f"{self.base_url}/embeddings"
        payload = {"model": model, "input": list(texts)}
        resp = self._transport(url, payload, self._headers(), self.timeout)
        items = resp.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise OpenAICompatError(
                f"Unexpected embeddings response shape from {url} (expected {len(texts)} items)"
            )
        ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
        return [[float(x) for x in item["embedding"]] for item in ordered]

    def chat_completion(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> str:
        """Request chat completion text via ``POST /chat/completions``."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = self._transport(url, payload, self._headers(), self.timeout)
        choices = resp.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAICompatError(f"Empty choices in chat completion from {url}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OpenAICompatError(f"Empty message content from {url}")
        return content.strip()
