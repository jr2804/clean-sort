"""A small HTTP client library — realistic module for preorder examples.

This file is intentionally out of order. Run::

    preorder diff tests/data/web_service_unsorted.py
    preorder run  tests/data/web_service_unsorted.py

to see section reordering, stepdown function sorting, and in-class method
ordering (undersort) in action.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import http.client  # noqa: F401  (only for type-checkers)

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
USER_AGENT = "pyreorder-demo/1.0"


class HttpStatus(enum.IntEnum):
    """Common HTTP status codes used by the client."""

    OK = 200
    NOT_FOUND = 404
    INTERNAL_ERROR = 500


class HttpMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


@dataclass
class Request:
    """A prepared HTTP request."""

    url: str
    method: HttpMethod = HttpMethod.GET
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None


@dataclass
class Response:
    """An HTTP response returned by :func:`send`."""

    status: HttpStatus
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


class HttpError(Exception):
    """Raised when a request fails after all retries."""

    def __init__(self, message: str, status: HttpStatus | None = None) -> None:
        super().__init__(message)
        self.status = status


class Client:
    """A minimal retrying HTTP client."""

    def __init__(self, base_url: str, *, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def request(self, req: Request) -> Response:
        """Send *req*, retrying on transient failures."""
        for attempt in range(MAX_RETRIES):
            try:
                return self._do_send(req)
            except TransientError:
                if attempt == MAX_RETRIES - 1:
                    raise
                LOGGER.warning("retrying (attempt %d)", attempt + 1)
        raise HttpError("unreachable")

    @classmethod
    def from_env(cls) -> Client:
        """Build a client configured from environment variables."""
        import os

        return cls(os.environ.get("API_BASE_URL", "http://localhost"))

    def _do_send(self, req: Request) -> Response:
        # In a real implementation this would open a socket; here we stub it.
        LOGGER.debug("sending %s %s", req.method, req.url)
        return Response(HttpStatus.OK, b"")


class TransientError(Exception):
    """Raised by :meth:`Client._do_send` on a retryable failure."""


def parse_retry_after(value: str | None) -> int:
    """Parse a Retry-After header into seconds (0 if absent / unparsable)."""
    if not value:
        return 0
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def main() -> None:
    """Demonstrate a simple GET request."""
    client = Client("https://example.com")
    response = send(client, "/health")
    print(f"status={response.status}")


def send(client: Client, path: str, *, method: HttpMethod = HttpMethod.GET) -> Response:
    """High-level convenience wrapper around :meth:`Client.request`."""
    req = Request(url=build_url(client._base_url, path), method=method)
    return client.request(req)


def build_url(base: str, path: str) -> str:
    """Join *base* and *path* into a single URL."""
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


if __name__ == "__main__":
    main()
