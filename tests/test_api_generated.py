"""client.api: every feature route, one method each, generated from the API spec
(scripts/apigen.sh). Calls go through the same ApiClient and credentials as every
resource method; the raw verbs client.api always had keep working."""

from __future__ import annotations

import json
from typing import List
from urllib.parse import parse_qs, urlsplit

import httpx

from forjio_linksnap import LinkSnapClient


def _client(seen: List[httpx.Request], api_key: str = "lsk_live_test") -> LinkSnapClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = {"data": {"ok": True}, "error": None, "meta": {"requestId": "r"}}
        return httpx.Response(200, content=json.dumps(body).encode())

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return LinkSnapClient(base_url="https://linksnap.test", api_key=api_key, http=http)


def test_create_sends_the_fields_linksnap_reads_with_the_client_credentials() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen)
    client.api.links_create(url="https://example.com", slug="spring", tags=["promo"])
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/links")
    assert json.loads(request.content) == {"url": "https://example.com", "slug": "spring", "tags": ["promo"]}
    # The same header every resource method of this SDK sends: the key as the server reads it.
    assert request.headers["authorization"] == "ApiKey lsk_live_test"


def test_path_and_query() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen)
    client.api.links_get("a b")
    client.api.links_list(limit=5, tag="promo")
    assert seen[0].url.raw_path.decode() == "/api/v1/links/a%20b"
    assert seen[1].url.path == "/api/v1/links"
    assert parse_qs(urlsplit(str(seen[1].url)).query) == {"limit": ["5"], "tag": ["promo"]}
    assert seen[1].content == b""


def test_the_raw_verbs_still_work() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen)
    client.api.patch("/api/v1/links/spring", {"domainId": "dom_1"}, auth_token="tok")
    assert (seen[0].method, seen[0].url.path) == ("PATCH", "/api/v1/links/spring")
    assert seen[0].headers["authorization"] == "Bearer tok"
    assert client.api.base_url == "https://linksnap.test"


def test_every_feature_route_has_a_method() -> None:
    api = _client([]).api
    methods = [n for n in vars(type(api).__mro__[1]) if not n.startswith("_")]
    assert len(methods) >= 50
    assert "qr_codes_create" in methods
