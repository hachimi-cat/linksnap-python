"""Resource namespaces for LinkSnapClient — Python parity with linksnap-node.

Each builder takes an ApiClient and returns a small object whose methods
map 1:1 to backend REST routes. Methods accept an optional `auth_token`
to override the client-level bearer for a single call — same shape as
the Node SDK's `(args, authToken?)` calling convention.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .http_client import ApiClient


def _opts(auth_token: Optional[str]) -> Dict[str, Any]:
    return {"auth_token": auth_token} if auth_token else {}


class _Namespace:
    def __init__(self, api: ApiClient, default_token: Optional[str] = None) -> None:
        self.api = api
        # Static API key acts as the default auth token when no per-call
        # token is supplied. Matches Node SDK's `this.a(authToken)` logic.
        self._default_token = default_token

    def _t(self, auth_token: Optional[str]) -> Optional[str]:
        return auth_token if auth_token is not None else self._default_token


class LinksResources(_Namespace):
    def list(
        self,
        *,
        tag: Optional[str] = None,
        archived: Optional[bool] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        return self.api.get(
            "/api/v1/links",
            query={"tag": tag, "archived": archived, "limit": limit, "cursor": cursor},
            **_opts(self._t(auth_token)),
        )

    def get(self, id_or_slug: str, *, auth_token: Optional[str] = None):
        return self.api.get(f"/api/v1/links/{id_or_slug}", **_opts(self._t(auth_token)))

    def create(self, body: Dict[str, Any], *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/links", body, **_opts(self._t(auth_token)))

    def update(self, id_or_slug: str, patch: Dict[str, Any], *, auth_token: Optional[str] = None):
        return self.api.patch(f"/api/v1/links/{id_or_slug}", patch, **_opts(self._t(auth_token)))

    def delete(self, id_or_slug: str, *, auth_token: Optional[str] = None):
        return self.api.delete(f"/api/v1/links/{id_or_slug}", **_opts(self._t(auth_token)))

    def bulk(self, action: str, ids: List[str], *, auth_token: Optional[str] = None):
        return self.api.post(
            "/api/v1/links/bulk", {"action": action, "ids": ids}, **_opts(self._t(auth_token))
        )

    def export(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/links/export", **_opts(self._t(auth_token)))

    def import_csv(self, csv: str, *, auth_token: Optional[str] = None):
        # Method named `import_csv` because `import` is a Python keyword.
        return self.api.post("/api/v1/links/import", {"csv": csv}, **_opts(self._t(auth_token)))


class StatsResources(_Namespace):
    def show(
        self,
        id_or_slug: str,
        *,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        return self.api.get(
            f"/api/v1/links/{id_or_slug}/stats",
            query={"from": from_, "to": to},
            **_opts(self._t(auth_token)),
        )

    def export(self, id_or_slug: str, *, auth_token: Optional[str] = None):
        return self.api.get(f"/api/v1/links/{id_or_slug}/stats/export", **_opts(self._t(auth_token)))

    def workspace(
        self,
        *,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        return self.api.get(
            "/api/v1/workspaces/current/stats",
            query={"from": from_, "to": to},
            **_opts(self._t(auth_token)),
        )


class QrResources(_Namespace):
    def list(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/qr-codes", **_opts(self._t(auth_token)))

    def get(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.get(f"/api/v1/qr-codes/{id}", **_opts(self._t(auth_token)))

    def create(self, body: Dict[str, Any], *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/qr-codes", body, **_opts(self._t(auth_token)))

    def delete(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.delete(f"/api/v1/qr-codes/{id}", **_opts(self._t(auth_token)))

    def download(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.get(f"/api/v1/qr-codes/{id}/download", **_opts(self._t(auth_token)))

    def stats(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.get(f"/api/v1/qr-codes/{id}/stats", **_opts(self._t(auth_token)))


class TagsResources(_Namespace):
    def list(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/tags", **_opts(self._t(auth_token)))


class DomainsResources(_Namespace):
    def list(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/domains", **_opts(self._t(auth_token)))

    def add(self, domain: str, *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/domains", {"domain": domain}, **_opts(self._t(auth_token)))

    def verify(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.post(f"/api/v1/domains/{id}/verify", None, **_opts(self._t(auth_token)))

    def remove(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.delete(f"/api/v1/domains/{id}", **_opts(self._t(auth_token)))


class BillingResources(_Namespace):
    def plans(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/billing/plans", **_opts(self._t(auth_token)))

    def plan(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/billing/plan", **_opts(self._t(auth_token)))

    def subscription(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/billing/subscription", **_opts(self._t(auth_token)))

    def usage(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/billing/usage", **_opts(self._t(auth_token)))

    def history(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/billing/history", **_opts(self._t(auth_token)))

    def invoices(self, *, limit: Optional[int] = None, auth_token: Optional[str] = None):
        return self.api.get(
            "/api/v1/billing/invoices", query={"limit": limit}, **_opts(self._t(auth_token))
        )

    def checkout(self, plan_id: str, *, auth_token: Optional[str] = None):
        return self.api.post(
            "/api/v1/billing/checkout", {"plan": plan_id}, **_opts(self._t(auth_token))
        )

    def cancel(self, *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/billing/cancel", None, **_opts(self._t(auth_token)))

    def downgrade(self, plan_id: str, *, auth_token: Optional[str] = None):
        return self.api.post(
            "/api/v1/billing/downgrade", {"plan": plan_id}, **_opts(self._t(auth_token))
        )


class WorkspaceMembersResources(_Namespace):
    def list(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/workspaces/current/members", **_opts(self._t(auth_token)))

    def add(self, email: str, *, role: Optional[str] = None, auth_token: Optional[str] = None):
        body: Dict[str, Any] = {"email": email}
        if role is not None:
            body["role"] = role
        return self.api.post("/api/v1/workspaces/current/members", body, **_opts(self._t(auth_token)))

    def remove(self, member_id: str, *, auth_token: Optional[str] = None):
        return self.api.delete(
            f"/api/v1/workspaces/current/members/{member_id}", **_opts(self._t(auth_token))
        )


class WorkspaceResources(_Namespace):
    def __init__(self, api: ApiClient, default_token: Optional[str] = None) -> None:
        super().__init__(api, default_token)
        self.members = WorkspaceMembersResources(api, default_token)

    def show(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/workspaces/current", **_opts(self._t(auth_token)))

    def rename(self, name: str, *, auth_token: Optional[str] = None):
        return self.api.patch(
            "/api/v1/workspaces/current", {"name": name}, **_opts(self._t(auth_token))
        )


class ApiKeysResources(_Namespace):
    def list(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/auth/api-keys", **_opts(self._t(auth_token)))

    def create(self, name: str, *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/auth/api-keys", {"name": name}, **_opts(self._t(auth_token)))

    def delete(self, id: str, *, auth_token: Optional[str] = None):
        return self.api.delete(f"/api/v1/auth/api-keys/{id}", **_opts(self._t(auth_token)))


class AccountResources(_Namespace):
    def me(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/auth/me", **_opts(self._t(auth_token)))

    def update(self, patch: Dict[str, Any], *, auth_token: Optional[str] = None):
        return self.api.patch("/api/v1/auth/me", patch, **_opts(self._t(auth_token)))

    def change_password(
        self, *, current_password: str, new_password: str, auth_token: Optional[str] = None
    ):
        return self.api.post(
            "/api/v1/auth/change-password",
            {"currentPassword": current_password, "newPassword": new_password},
            **_opts(self._t(auth_token)),
        )

    def delete(self, *, auth_token: Optional[str] = None):
        return self.api.delete("/api/v1/auth/account", **_opts(self._t(auth_token)))


def build_resources(api: ApiClient, default_token: Optional[str] = None) -> Dict[str, _Namespace]:
    return {
        "links": LinksResources(api, default_token),
        "stats": StatsResources(api, default_token),
        "qr": QrResources(api, default_token),
        "tags": TagsResources(api, default_token),
        "domains": DomainsResources(api, default_token),
        "billing": BillingResources(api, default_token),
        "workspace": WorkspaceResources(api, default_token),
        "api_keys": ApiKeysResources(api, default_token),
        "account": AccountResources(api, default_token),
    }
