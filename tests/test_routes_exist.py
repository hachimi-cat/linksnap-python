"""Every hand-written method calls a route the backend really has.

The spec (backend/openapi.json) is made from the backend's own code by
scripts/apigen.sh, so a method pointing at a route that was renamed or never
existed fails here instead of 404ing for a customer. (client.api is generated
from the same spec.)"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any, Iterator, List, Set, Tuple

import httpx
import pytest

from forjio_linksnap import LinkSnapClient
from forjio_linksnap.http_client import ApiClient

SPEC = Path(__file__).resolve().parents[3] / "backend" / "openapi.json"


def _routes() -> Set[str]:
    paths = json.loads(SPEC.read_text())["paths"]
    return {
        f"{method.upper()} {re.sub(r'{[^}]+}', '{}', path)}"
        for path, ops in paths.items()
        for method in ops
    }


def _methods(obj: Any, prefix: str) -> Iterator[Tuple[str, Any]]:
    """Public methods of a resource namespace, and of the namespaces under it (not the
    ApiClient each one holds)."""
    for name, value in vars(obj).items():
        if name.startswith("_") or isinstance(value, ApiClient):
            continue
        yield from _methods(value, f"{prefix}{name}.")
    for name, fn in inspect.getmembers(type(obj), inspect.isfunction):
        if not name.startswith("_"):
            yield f"{prefix}{name}", getattr(obj, name)


def _placeholder_call(fn: Any) -> None:
    """Call with a placeholder for every required parameter: "__0__", "__1__" stand
    for ids in the path."""
    args: List[Any] = []
    kwargs = {}
    for i, p in enumerate(inspect.signature(fn).parameters.values()):
        if p.default is not inspect.Parameter.empty or p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL):
            continue
        # A dict parameter (a body) gets an empty one, a list an empty list; the rest are ids.
        ann = str(p.annotation)
        value: Any = {} if "Dict" in ann else [] if "List" in ann else f"__{i}__"
        if p.kind is p.KEYWORD_ONLY:
            kwargs[p.name] = value
        else:
            args.append(value)
    fn(*args, **kwargs)


@pytest.mark.skipif(not SPEC.exists(), reason="no backend/openapi.json beside this SDK (a public mirror)")
def test_every_hand_written_method_calls_a_route_in_the_spec() -> None:
    routes = _routes()
    seen: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = re.sub(r"__\d__", "{}", request.url.path)
        seen.append(f"{request.method} {path}")
        return httpx.Response(200, json={"data": {}, "error": None, "meta": {"requestId": "r"}})

    client = LinkSnapClient(
        api_key="lsk_test_x",
        base_url="https://linksnap.test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    namespaces = {k: v for k, v in vars(client).items() if not k.startswith("_") and k not in ("api", "base_url")}
    methods = [m for name, ns in namespaces.items() for m in _methods(ns, f"{name}.")]
    methods.append(("health", client.health))
    assert len(methods) > 35

    missing = []
    for name, fn in methods:
        seen.clear()
        _placeholder_call(fn)
        assert len(seen) == 1, name
        if seen[0] not in routes:
            missing.append(f"{name}: {seen[0]}")
    assert missing == []
