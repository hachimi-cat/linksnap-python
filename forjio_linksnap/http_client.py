"""Typed HTTP client for LinkSnap.

Bearer auth (an API key as ``ApiKey <key>``), proactive refresh (~5min before expiry), reactive single
retry on 401 with refresh in between, envelope unwrap (Forjio
data/error/meta shape), auto-pagination.

Mirrors `@forjio/sdk`'s ApiClient — same behaviour as the Huudis Python
SDK so consumers get identical semantics across the Forjio family.
"""

from __future__ import annotations

import mimetypes
import os
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .errors import LinkSnapError, NetworkError
from .session import Session


def authorization_header(token: str) -> str:
    """A LinkSnap API key (``lsk_live_…`` / ``lsk_test_…``) goes as ``ApiKey <key>``, which
    is what the server reads; a session / OIDC access token as ``Bearer <token>``."""
    return f"ApiKey {token}" if token.startswith("lsk_") else f"Bearer {token}"


class ApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        session: Optional[Session] = None,
        http: Optional[httpx.Client] = None,
        refresh_buffer_sec: int = 300,
        retry_on_5xx: int = 1,
        default_headers: Optional[Dict[str, str]] = None,
        default_query: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session
        self._http = http or httpx.Client(timeout=10.0)
        self._owns_http = http is None
        self.refresh_buffer_sec = refresh_buffer_sec
        self.retry_on_5xx = retry_on_5xx
        self.default_headers = default_headers or {}
        self.default_query = default_query or {}

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- public methods ---------------------------------------------------

    def get(self, path: str, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("GET", path, None, query=query, headers=headers, auth_token=auth_token)

    def post(self, path: str, body: Any = None, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("POST", path, body, query=query, headers=headers, auth_token=auth_token)

    def patch(self, path: str, body: Any = None, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("PATCH", path, body, query=query, headers=headers, auth_token=auth_token)

    def put(self, path: str, body: Any = None, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("PUT", path, body, query=query, headers=headers, auth_token=auth_token)

    def delete(self, path: str, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("DELETE", path, None, query=query, headers=headers, auth_token=auth_token)

    def paginate(
        self,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        cursor_param: str = "cursor",
        auth_token: Optional[str] = None,
    ) -> Iterator[Any]:
        cursor: Optional[str] = None
        while True:
            q = dict(query or {})
            if cursor:
                q[cursor_param] = cursor
            page = self.get(path, query=q, auth_token=auth_token)
            for item in _extract_items(page):
                yield item
            cursor = _extract_cursor(page)
            if not cursor:
                return

    # ---- internals --------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: Any,
        *,
        query: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        auth_token: Optional[str],
        form: Optional[Mapping[str, Any]] = None,
        files: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """``body`` is sent as JSON; ``form`` fields and ``files`` (a file upload) as
        multipart/form-data. Each file is read once, so a retry sends the same bytes."""
        multipart = None
        if form is not None or files is not None:
            multipart = (
                {k: v if isinstance(v, str) else _form_value(v) for k, v in (form or {}).items() if v is not None},
                {k: _file_part(k, v) for k, v in (files or {}).items() if v is not None},
            )
        # Proactive refresh
        if self.session is not None and auth_token is None and self.session.will_expire_soon(self.refresh_buffer_sec):
            try:
                self.session.refresh()
            except Exception:
                pass
        res = self._send(method, path, body, query=query, headers=headers, auth_token=auth_token, multipart=multipart)
        # Reactive single 401 retry
        if res.status_code == 401 and self.session is not None and auth_token is None:
            try:
                self.session.refresh()
                res = self._send(method, path, body, query=query, headers=headers, auth_token=auth_token, multipart=multipart)
            except Exception:
                pass
        # 5xx retry
        retries_left = self.retry_on_5xx
        while res.status_code >= 500 and retries_left > 0:
            retries_left -= 1
            res = self._send(method, path, body, query=query, headers=headers, auth_token=auth_token, multipart=multipart)
        return self._unwrap(res)

    def _send(
        self,
        method: str,
        path: str,
        body: Any,
        *,
        query: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        auth_token: Optional[str],
        multipart: Optional[Tuple[Dict[str, str], Dict[str, Tuple[str, bytes, str]]]] = None,
    ) -> httpx.Response:
        if urlparse(path).scheme:
            url = path
        else:
            url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        merged_q: Dict[str, Any] = dict(self.default_query)
        if query:
            merged_q.update({k: v for k, v in query.items() if v is not None})
        h: Dict[str, str] = dict(self.default_headers)
        h["accept"] = h.get("accept", "application/json")
        if headers:
            h.update(headers)
        token = auth_token or (self.session.data.access_token if (self.session and self.session.data) else None)
        if token:
            h["authorization"] = authorization_header(token)
        kwargs: Dict[str, Any] = {"params": merged_q or None, "headers": h}
        if multipart is not None:
            # httpx writes the multipart body and its Content-Type (with the boundary)
            h.pop("content-type", None)
            kwargs["data"] = multipart[0] or None
            kwargs["files"] = multipart[1]
        elif body is not None:
            h.setdefault("content-type", "application/json")
            kwargs["json"] = body
        try:
            return self._http.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            raise NetworkError(str(e)) from e

    def _unwrap(self, res: httpx.Response) -> Any:
        text = res.text or ""
        parsed: Any = None
        if text:
            try:
                parsed = res.json()
            except Exception:
                if res.status_code >= 400:
                    raise LinkSnapError("NON_JSON_ERROR", text or res.reason_phrase, res.status_code)
                raise LinkSnapError("INVALID_RESPONSE", "non-JSON response", res.status_code)
        if isinstance(parsed, dict) and "data" in parsed and "error" in parsed and "meta" in parsed:
            if parsed.get("error"):
                error = parsed["error"]
                raise LinkSnapError(
                    error.get("code", "UNKNOWN"),
                    error.get("message", ""),
                    res.status_code,
                    request_id=(parsed.get("meta") or {}).get("requestId"),
                    details=error.get("details"),
                )
            return parsed.get("data")
        if res.status_code >= 400:
            err_obj = parsed.get("error") if isinstance(parsed, dict) else parsed
            code = (err_obj or {}).get("code", "HTTP_ERROR") if isinstance(err_obj, dict) else "HTTP_ERROR"
            message = (err_obj or {}).get("message", res.reason_phrase) if isinstance(err_obj, dict) else res.reason_phrase
            raise LinkSnapError(code, message, res.status_code, details=parsed if isinstance(parsed, dict) else None)
        return parsed


def _form_value(value: Any) -> str:
    import json

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, separators=(",", ":"))


def _file_part(field: str, value: Any) -> Tuple[str, bytes, str]:
    """A file as httpx sends it: (filename, content, content type). ``value`` is bytes, a
    binary file object, or a (filename, content[, content_type]) tuple. A part without a
    type gets one from its file name — the server takes a file by its declared type (the
    QR logo: PNG, JPEG or SVG only)."""
    name: Optional[str] = None
    content_type: Optional[str] = None
    if isinstance(value, tuple):
        name = value[0]
        content = value[1]
        content_type = value[2] if len(value) > 2 else None
    else:
        content = value
    if hasattr(content, "read"):
        if name is None:
            name = os.path.basename(str(getattr(content, "name", "") or "")) or None
        content = content.read()
    if isinstance(content, str):
        content = content.encode("utf-8")
    name = name or field
    content_type = content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    return (name, bytes(content), content_type)


def _extract_items(page: Any) -> Iterator[Any]:
    if isinstance(page, list):
        yield from page
        return
    if isinstance(page, dict):
        for key in ("items", "data", "results"):
            v = page.get(key)
            if isinstance(v, list):
                yield from v
                return


def _extract_cursor(page: Any) -> Optional[str]:
    if not isinstance(page, dict):
        return None
    nc = page.get("nextCursor")
    if isinstance(nc, str) and nc:
        return nc
    meta = page.get("meta")
    if isinstance(meta, dict):
        mc = meta.get("nextCursor")
        if isinstance(mc, str) and mc:
            return mc
    return None
