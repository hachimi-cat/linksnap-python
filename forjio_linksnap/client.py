"""High-level LinkSnap client — Python parity with linksnap-node.

Wraps every developer-facing endpoint behind resource namespaces:
links, stats, qr, tags, domains, billing, workspace (+ members),
api_keys, account, plus an unauthenticated `health()` ping.

Auth model (mirrors the Node SDK):

- Pass `session=` (a `Session` from this SDK) and the client will attach
  the session's bearer token to every request and refresh as needed.
- Pass `api_key=` to attach a static bearer (e.g. CI / headless runs).
- Pass `auth_token=` on a single call to override either of the above.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .http_client import ApiClient
from .resources import (
    AccountResources,
    ApiKeysResources,
    BillingResources,
    DomainsResources,
    LinksResources,
    QrResources,
    StatsResources,
    TagsResources,
    WorkspaceResources,
    build_resources,
)
from .session import Session


class LinkSnapClient:
    """Resource-namespaced LinkSnap client.

    Use as a context manager (`with LinkSnapClient(...) as ls: ...`) or
    call `.close()` to release the owned `httpx.Client`.
    """

    # Type hints for IDE completion — populated in __init__
    links: LinksResources
    stats: StatsResources
    qr: QrResources
    tags: TagsResources
    domains: DomainsResources
    billing: BillingResources
    workspace: WorkspaceResources
    api_keys: ApiKeysResources
    account: AccountResources

    def __init__(
        self,
        *,
        base_url: str = "https://linksnap.forjio.com",
        session: Optional[Session] = None,
        api_key: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=10.0)
        self._owns_http = http is None
        self.api = ApiClient(base_url=self.base_url, session=session, http=self._http)
        self._api_key = api_key
        resources = build_resources(self.api, default_token=api_key)
        self.links = resources["links"]  # type: ignore[assignment]
        self.stats = resources["stats"]  # type: ignore[assignment]
        self.qr = resources["qr"]  # type: ignore[assignment]
        self.tags = resources["tags"]  # type: ignore[assignment]
        self.domains = resources["domains"]  # type: ignore[assignment]
        self.billing = resources["billing"]  # type: ignore[assignment]
        self.workspace = resources["workspace"]  # type: ignore[assignment]
        self.api_keys = resources["api_keys"]  # type: ignore[assignment]
        self.account = resources["account"]  # type: ignore[assignment]

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "LinkSnapClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ─── Health (no auth) ────────────────────────────────────────────────

    def health(self) -> Any:
        return self.api.get("/api/v1/health")
