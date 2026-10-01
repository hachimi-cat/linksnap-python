"""High-level LinkSnap client — Python parity with linksnap-node.

Wraps every developer-facing endpoint behind resource namespaces:
links, stats, qr, tags, domains, billing, workspace (+ members),
api_keys, account, plus an unauthenticated `health()` ping.

Auth model (mirrors the Node SDK):

- Pass `session=` (a `Session` from this SDK) and the client will attach
  the session's bearer token to every request and refresh as needed.
- Pass `api_key=` (the workspace's `lsk_live_…` key; CI / headless runs) and every
  request carries `Authorization: ApiKey <key>`.
- Pass `auth_token=` on a single call to override either of the above.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from .api_generated import GeneratedApi
from .http_client import ApiClient, authorization_header
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


class LinkSnapApi(GeneratedApi):
    """``client.api``: every feature route, one method each (``api_generated.py``,
    generated from the API spec) — and, as before, the underlying ``ApiClient``'s own
    ``get`` / ``post`` / ``patch`` / ``put`` / ``delete`` / ``paginate``
    (``client.api.get("/api/v1/...")``), which the docs offer as the escape hatch."""

    def __init__(self, client: "LinkSnapClient", http_api: ApiClient) -> None:
        super().__init__(client)
        self._http_api = http_api

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._http_api, name)


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
        # A key is the credential for every call (the raw verbs of client.api included) and
        # takes precedence over a session.
        self._api_client = ApiClient(
            base_url=self.base_url,
            session=None if api_key else session,
            http=self._http,
            default_headers={"authorization": authorization_header(api_key)} if api_key else None,
        )
        self._api_key = api_key
        # Every feature route, one method each (generated from the API spec), plus the
        # raw HTTP verbs client.api always had.
        self.api = LinkSnapApi(self, self._api_client)
        resources = build_resources(self._api_client, default_token=api_key)
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
        return self._api_client.get("/api/v1/health")

    # ─── Generated routes ─────────────────────────────────────────────────

    def _apigen_request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        body: Any = None,
        form: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """The call behind ``client.api.<area>_<action>(...)`` (api_generated.py): the
        same ApiClient and credentials (session, or the constructor's ``api_key``) as
        every resource method. A file upload (``form=`` / ``files=``) is sent as
        multipart/form-data."""
        verb = method.upper()
        if form is not None or files is not None:
            return self._api_client._request(
                verb, path, None, query=query, headers=None, auth_token=self._api_key or None, form=form, files=files
            )
        if verb in ("POST", "PATCH", "PUT"):
            return getattr(self._api_client, verb.lower())(path, body, query=query, auth_token=self._api_key or None)
        if verb in ("GET", "DELETE"):
            return getattr(self._api_client, verb.lower())(path, query=query, auth_token=self._api_key or None)
        raise ValueError(f"unsupported method {method}")
