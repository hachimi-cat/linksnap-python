"""A file upload through the generated surface (client.api.qr_codes_upload_logo): sent as
multipart/form-data with the client's credential; a retry after a 5xx sends the same bytes."""

from __future__ import annotations

import io
import json
from email.parser import BytesParser
from email.policy import default
from typing import Dict, List, Tuple

import httpx
import pytest

from forjio_linksnap import LinkSnapClient
from forjio_linksnap.errors import LinkSnapError

PNG = b"\x89PNG\r\n\x1a\n"


def _parts(request: httpx.Request) -> Dict[str, Tuple[str, str, bytes]]:
    """field -> (filename, content type, bytes), parsed like a server would."""
    raw = b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + request.content
    msg = BytesParser(policy=default).parsebytes(raw)
    out = {}
    for part in msg.iter_parts():
        out[part.get_param("name", header="content-disposition")] = (
            part.get_filename(),
            part.get_content_type(),
            part.get_payload(decode=True),
        )
    return out


def _client(seen: List[httpx.Request], answers: List[httpx.Response], api_key: str = "lsk_live_test") -> LinkSnapClient:
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        seen.append(request)
        return answers.pop(0)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return LinkSnapClient(base_url="https://linksnap.test", api_key=api_key, http=http)


def _ok(data: object) -> httpx.Response:
    return httpx.Response(200, content=json.dumps({"data": data, "error": None, "meta": {"requestId": "r"}}).encode())


def test_logo_upload_is_multipart_with_the_api_key() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen, [_ok({"logoData": "data:image/png;base64,AA=="})])
    out = client.api.qr_codes_upload_logo(logo=("logo.png", PNG, "image/png"))
    assert out == {"logoData": "data:image/png;base64,AA=="}
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/qr-codes/upload-logo")
    assert request.headers["authorization"] == "ApiKey lsk_live_test"
    assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert _parts(request) == {"logo": ("logo.png", "image/png", PNG)}


def test_a_file_object_keeps_its_name_and_gets_a_type_from_it() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen, [_ok({})])
    f = io.BytesIO(b"<svg/>")
    f.name = "/tmp/brand/mark.svg"
    client.api.qr_codes_upload_logo(logo=f)
    assert _parts(seen[0]) == {"logo": ("mark.svg", "image/svg+xml", b"<svg/>")}


def test_bytes_alone_are_sent_under_the_field_name() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen, [_ok({})])
    client.api.qr_codes_upload_logo(logo=PNG)
    name, ctype, content = _parts(seen[0])["logo"]
    assert (name, content) == ("logo", PNG)


def test_a_retry_after_a_5xx_sends_the_same_file() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen, [httpx.Response(502, content=b"bad gateway"), _ok({})])
    f = io.BytesIO(PNG)
    f.name = "logo.png"
    client.api.qr_codes_upload_logo(logo=f)
    assert len(seen) == 2
    assert _parts(seen[1]) == _parts(seen[0]) == {"logo": ("logo.png", "image/png", PNG)}


def test_the_servers_refusal_is_raised() -> None:
    seen: List[httpx.Request] = []
    refusal = {"data": None, "error": {"code": "FORBIDDEN", "message": "QR logo is available on Pro and Business plans only"}, "meta": {"requestId": "req_1"}}
    client = _client(seen, [httpx.Response(403, content=json.dumps(refusal).encode())])
    with pytest.raises(LinkSnapError) as e:
        client.api.qr_codes_upload_logo(logo=("logo.png", PNG))
    assert (e.value.code, e.value.status) == ("FORBIDDEN", 403)
