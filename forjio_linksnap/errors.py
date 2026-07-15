"""Typed error classes for the LinkSnap SDK.

Mirrors the Node SDK's `LinkSnapError` (which re-exports `@forjio/sdk`'s
`ApiError`). The Python SDK also exposes auxiliary error types used by
the session / device-flow helpers — same shape as the Huudis Python SDK.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class LinkSnapAuthError(Exception):
    """Raised on LinkSnap auth / OIDC failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"LinkSnapAuthError({self.code!r}, {self.message!r})"


class RefreshError(Exception):
    """Raised when refreshing an OIDC access token fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"RefreshError({self.code!r}, {self.message!r})"


class NetworkError(Exception):
    """Raised on transport failures (DNS, connect refused, TLS, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LinkSnapError(Exception):
    """Raised on enveloped errors (data=null, error.code/message) or
    non-2xx HTTP responses from LinkSnap APIs.

    Parity with the Node SDK's `LinkSnapError` (= `@forjio/sdk` `ApiError`).
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        *,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.request_id = request_id
        self.details = details

    def __repr__(self) -> str:
        return f"LinkSnapError({self.code!r}, {self.message!r}, status={self.status})"


# Backwards/parity alias: callers may prefer the generic name.
ApiError = LinkSnapError
