"""Smoke tests for LinkSnapClient — Python parity with linksnap-node tests.

Mocks httpx so each resource method is verified to hit the right path
with the right verb + body. Mirrors `test/resources.test.ts` in the Node
SDK plus a few Python-specific checks (construction defaults, error
unwrap, respx-based round-trip).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import httpx
import pytest
import respx

from forjio_linksnap import (
    ApiClient,
    LinkSnapClient,
    LinkSnapError,
    Session,
)


def _envelope(data: Any, *, error: Any = None, request_id: str = "req_test") -> bytes:
    return json.dumps(
        {"data": data, "error": error, "meta": {"requestId": request_id, "timestamp": "now"}}
    ).encode()


def _make_client(*, api_key: str = "lk_test") -> Tuple[LinkSnapClient, List[Dict[str, Any]]]:
    captured: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode() if request.method in {"POST", "PATCH", "PUT"} else None
        captured.append(
            {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "body": body,
            }
        )
        return httpx.Response(200, content=_envelope({"ok": True}))

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=5.0)
    client = LinkSnapClient(base_url="https://linksnap.test", api_key=api_key, http=http)
    return client, captured


# ─── construction ─────────────────────────────────────────────────────


def test_construction_defaults_to_linksnap_com():
    client = LinkSnapClient()
    assert client.base_url == "https://linksnap.forjio.com"
    client.close()


def test_construction_strips_trailing_slash():
    client = LinkSnapClient(base_url="https://linksnap.test/")
    assert client.base_url == "https://linksnap.test"
    client.close()


# ─── route round-trips ────────────────────────────────────────────────


def test_links_create_posts():
    client, captured = _make_client()
    client.links.create({"url": "https://example.com"})
    c = captured[0]
    assert c["method"] == "POST"
    assert "/api/v1/links" in c["url"]
    assert json.loads(c["body"]) == {"url": "https://example.com"}


def test_links_update_patches():
    client, captured = _make_client()
    client.links.update("slug_1", {"title": "New"})
    c = captured[0]
    assert c["method"] == "PATCH"
    assert "/api/v1/links/slug_1" in c["url"]
    assert json.loads(c["body"]) == {"title": "New"}


def test_links_bulk_posts():
    client, captured = _make_client()
    client.links.bulk("delete", ["l_1", "l_2"])
    c = captured[0]
    assert c["method"] == "POST"
    assert "/api/v1/links/bulk" in c["url"]
    assert json.loads(c["body"]) == {"action": "delete", "ids": ["l_1", "l_2"]}


def test_links_list_query():
    client, captured = _make_client()
    client.links.list(tag="ads", limit=25)
    url = captured[0]["url"]
    assert "/api/v1/links" in url
    assert "tag=ads" in url
    assert "limit=25" in url


def test_stats_show_gets():
    client, captured = _make_client()
    client.stats.show("slug_1")
    assert "/api/v1/links/slug_1/stats" in captured[0]["url"]
    assert captured[0]["method"] == "GET"


def test_qr_create_posts():
    client, captured = _make_client()
    client.qr.create({"url": "https://x.com"})
    assert "/api/v1/qr-codes" in captured[0]["url"]
    assert captured[0]["method"] == "POST"


def test_domains_verify_posts():
    client, captured = _make_client()
    client.domains.verify("dom_1")
    assert "/api/v1/domains/dom_1/verify" in captured[0]["url"]
    assert captured[0]["method"] == "POST"


def test_billing_checkout_posts():
    client, captured = _make_client()
    client.billing.checkout("pro")
    assert "/api/v1/billing/checkout" in captured[0]["url"]
    assert json.loads(captured[0]["body"]) == {"planId": "pro"}


def test_workspace_members_add_posts():
    client, captured = _make_client()
    client.workspace.members.add("a@b.com", role="admin")
    assert "/api/v1/workspaces/current/members" in captured[0]["url"]
    assert json.loads(captured[0]["body"]) == {"email": "a@b.com", "role": "admin"}


def test_workspace_members_remove_deletes():
    client, captured = _make_client()
    client.workspace.members.remove("m_1")
    assert captured[0]["method"] == "DELETE"
    assert "/api/v1/workspaces/current/members/m_1" in captured[0]["url"]


def test_api_keys_create_posts():
    client, captured = _make_client()
    client.api_keys.create("CI key")
    assert "/api/v1/auth/api-keys" in captured[0]["url"]
    assert json.loads(captured[0]["body"]) == {"name": "CI key"}


def test_account_change_password_posts():
    client, captured = _make_client()
    client.account.change_password(current_password="a", new_password="b")
    assert "/api/v1/auth/change-password" in captured[0]["url"]
    assert json.loads(captured[0]["body"]) == {"currentPassword": "a", "newPassword": "b"}


def test_tags_list_gets():
    client, captured = _make_client()
    client.tags.list()
    assert "/api/v1/tags" in captured[0]["url"]
    assert captured[0]["method"] == "GET"


# ─── auth attachment ──────────────────────────────────────────────────


def test_attaches_bearer_from_api_key_constructor_opt():
    client, captured = _make_client(api_key="lk_test")
    client.links.list()
    assert captured[0]["headers"]["authorization"] == "Bearer lk_test"


def test_per_call_auth_token_overrides_constructor_key():
    client, captured = _make_client(api_key="lk_test")
    client.links.list(auth_token="override_tok")
    assert captured[0]["headers"]["authorization"] == "Bearer override_tok"


def test_session_bearer_attaches_when_no_api_key():
    captured: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append({"headers": dict(request.headers)})
        return httpx.Response(200, content=_envelope({"ok": True}))

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=5.0)

    # Hand-build a session with in-memory data (skip filesystem).
    sess = Session(brand="linksnap", profile="test", credentials_path="/tmp/_doesnotexist")
    from forjio_linksnap import ProfileData

    sess._data = ProfileData(  # type: ignore[attr-defined]
        access_token="sess_tok",
        expires_at=2_000_000_000,
        issuer="https://huudis.test",
        client_id="cli_lk",
    )
    client = LinkSnapClient(base_url="https://linksnap.test", session=sess, http=http)
    client.links.list()
    assert captured[0]["headers"]["authorization"] == "Bearer sess_tok"


def test_health_uses_no_auth_when_no_key_no_session():
    captured: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append({"url": str(request.url), "headers": dict(request.headers)})
        return httpx.Response(200, content=_envelope({"status": "ok"}))

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=5.0)
    client = LinkSnapClient(base_url="https://linksnap.test", http=http)
    client.health()
    assert "/api/v1/health" in captured[0]["url"]
    assert "authorization" not in captured[0]["headers"]


# ─── errors ───────────────────────────────────────────────────────────


def test_envelope_error_raises_linksnap_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            content=_envelope(
                None,
                error={"code": "BAD_INPUT", "message": "url required"},
                request_id="req_99",
            ),
        )

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=5.0)
    client = LinkSnapClient(base_url="https://linksnap.test", http=http)
    with pytest.raises(LinkSnapError) as exc:
        client.links.create({})
    assert exc.value.code == "BAD_INPUT"
    assert exc.value.status == 400
    assert exc.value.request_id == "req_99"


# ─── respx-based round-trip ───────────────────────────────────────────


@respx.mock(base_url="https://linksnap.test")
def test_links_create_via_respx(respx_mock):
    route = respx_mock.post("/api/v1/links").mock(
        return_value=httpx.Response(
            200, content=_envelope({"id": "lnk_1", "slug": "abc", "url": "https://x.com"})
        )
    )
    client = LinkSnapClient(base_url="https://linksnap.test", api_key="lk_test")
    try:
        result = client.links.create({"url": "https://x.com"})
    finally:
        client.close()
    assert route.called
    assert result == {"id": "lnk_1", "slug": "abc", "url": "https://x.com"}
