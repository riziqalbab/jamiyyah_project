"""Dependency-free OpenAI-compatible HTTP client for Embeddings and Chat Completions."""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
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


_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_OLLAMA_TRANSIENT_MARKERS = (
    "health resp:",
    "do embedding request:",
    "connection refused",
    "forcibly closed",
    "wsarecv:",
)


def _is_retryable_http_error(status: int, raw: str) -> bool:
    """Return True for transient server/runner errors worth retrying."""
    if status in _RETRYABLE_STATUS_CODES:
        return True
    if status == 400:
        lowered = raw.lower()
        return any(marker in lowered for marker in _OLLAMA_TRANSIENT_MARKERS)
    return False


class _KeepAliveTransport:
    """Thread-local HTTP/HTTPS keep-alive transport for low-overhead batching."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _get_conn(
        self,
        scheme: str,
        netloc: str,
        timeout: float,
    ) -> http.client.HTTPConnection:
        conns: dict[tuple[str, str], http.client.HTTPConnection] = getattr(
            self._local, "conns", {}
        )
        if not hasattr(self._local, "conns"):
            self._local.conns = conns
        key = (scheme, netloc)
        conn = conns.get(key)
        if conn is not None:
            conn.timeout = timeout
            return conn
        if scheme == "https":
            conn = http.client.HTTPSConnection(netloc, timeout=timeout)
        elif scheme == "http":
            conn = http.client.HTTPConnection(netloc, timeout=timeout)
        else:
            raise OpenAICompatError(f"Unsupported URL scheme: {scheme}")
        conns[key] = conn
        return conn

    def _drop_conn(self, scheme: str, netloc: str) -> None:
        conns: dict[tuple[str, str], http.client.HTTPConnection] | None = getattr(
            self._local, "conns", None
        )
        if not conns:
            return
        conn = conns.pop((scheme, netloc), None)
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass

    def __call__(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        body = json.dumps(payload).encode("utf-8")
        req_headers = dict(headers)
        req_headers.setdefault("Connection", "keep-alive")

        last_exc: Exception | None = None
        max_attempts = 4
        for attempt in range(max_attempts):
            conn = self._get_conn(parsed.scheme, parsed.netloc, timeout)
            try:
                conn.request("POST", path, body=body, headers=req_headers)
                resp = conn.getresponse()
                raw = resp.read().decode("utf-8", errors="replace")
            except (http.client.HTTPException, OSError, TimeoutError) as exc:
                self._drop_conn(parsed.scheme, parsed.netloc)
                last_exc = exc
                if attempt + 1 < max_attempts:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise OpenAICompatError(f"Connection failed to {url}: {exc}") from exc

            if resp.status >= 400:
                if _is_retryable_http_error(resp.status, raw) and attempt + 1 < max_attempts:
                    self._drop_conn(parsed.scheme, parsed.netloc)
                    last_exc = OpenAICompatError(f"HTTP {resp.status} from {url}: {raw[:300]}")
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise OpenAICompatError(f"HTTP {resp.status} from {url}: {raw[:300]}")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise OpenAICompatError(f"Invalid JSON response from {url}") from exc

        raise OpenAICompatError(f"Connection failed to {url}: {last_exc}")


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
        self._transport = transport or _KeepAliveTransport()

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
        try:
            resp = self._transport(url, payload, self._headers(), self.timeout)
        except OpenAICompatError:
            if len(texts) > 1:
                mid = len(texts) // 2
                return self.embed(texts[:mid], model=model) + self.embed(
                    texts[mid:], model=model
                )
            raise
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
