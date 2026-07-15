"""OIDC Device Authorization Grant (RFC 8628) for CLI sign-in.

Mirror of `@forjio/sdk`'s auth/device-flow.ts so Python and Node SDKs feel
identical at the call site. When a central forjio-sdk-py is later
extracted, this module moves there unchanged.

LinkSnap uses Huudis as its OIDC issuer — the discovery endpoint is the
Huudis issuer URL the CLI/SDK is configured against.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import httpx

from .errors import LinkSnapAuthError, RefreshError


@dataclass
class DiscoveryDocument:
    issuer: str
    device_authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    authorization_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    end_session_endpoint: Optional[str] = None


@dataclass
class DeviceFlowStart:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int
    verification_uri_complete: Optional[str] = None


@dataclass
class DeviceTokens:
    access_token: str
    expires_at: int  # unix epoch seconds
    token_type: str = "Bearer"
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


_DISCOVERY_CACHE: Dict[str, DiscoveryDocument] = {}


def clear_discovery_cache() -> None:
    """For tests."""
    _DISCOVERY_CACHE.clear()


def _http() -> httpx.Client:
    return httpx.Client(timeout=10.0)


def fetch_discovery(issuer: str, *, http: Optional[httpx.Client] = None) -> DiscoveryDocument:
    cached = _DISCOVERY_CACHE.get(issuer)
    if cached:
        return cached
    client = http or _http()
    try:
        url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        res = client.get(url)
    except httpx.HTTPError as e:
        raise LinkSnapAuthError("DISCOVERY_FAILED", f"OIDC discovery network error: {e}") from e
    finally:
        if http is None:
            client.close()
    if res.status_code >= 400:
        raise LinkSnapAuthError("DISCOVERY_FAILED", f"OIDC discovery failed: {res.status_code}")
    payload = res.json()
    if not payload.get("device_authorization_endpoint") or not payload.get("token_endpoint"):
        raise LinkSnapAuthError("DISCOVERY_INCOMPLETE", "OIDC discovery missing required endpoints")
    doc = DiscoveryDocument(
        issuer=payload.get("issuer", issuer),
        device_authorization_endpoint=payload["device_authorization_endpoint"],
        token_endpoint=payload["token_endpoint"],
        jwks_uri=payload["jwks_uri"],
        authorization_endpoint=payload.get("authorization_endpoint"),
        userinfo_endpoint=payload.get("userinfo_endpoint"),
        end_session_endpoint=payload.get("end_session_endpoint"),
    )
    _DISCOVERY_CACHE[issuer] = doc
    return doc


def start_device_flow(
    *,
    issuer: str,
    client_id: str,
    scope: Optional[str] = None,
    http: Optional[httpx.Client] = None,
) -> DeviceFlowStart:
    disco = fetch_discovery(issuer, http=http)
    body = {"client_id": client_id}
    if scope:
        body["scope"] = scope
    client = http or _http()
    try:
        res = client.post(
            disco.device_authorization_endpoint,
            data=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError as e:
        raise LinkSnapAuthError("DEVICE_AUTH_NETWORK_ERROR", str(e)) from e
    finally:
        if http is None:
            client.close()
    if res.status_code >= 400:
        raise LinkSnapAuthError("DEVICE_AUTH_FAILED", f"{res.status_code}: {res.text}")
    payload: Dict[str, Any] = res.json()
    return DeviceFlowStart(
        device_code=payload["device_code"],
        user_code=payload["user_code"],
        verification_uri=payload["verification_uri"],
        verification_uri_complete=payload.get("verification_uri_complete"),
        expires_in=int(payload["expires_in"]),
        interval=int(payload.get("interval", 5)),
    )


def poll_device_token(
    *,
    issuer: str,
    client_id: str,
    device_code: str,
    interval: int = 5,
    on_pending: Optional[Callable[[], None]] = None,
    http: Optional[httpx.Client] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> DeviceTokens:
    disco = fetch_discovery(issuer, http=http)
    client = http or _http()
    try:
        cur_interval = interval
        while True:
            sleep(cur_interval)
            res = client.post(
                disco.token_endpoint,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": client_id,
                },
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            payload = _safe_json(res)
            if res.status_code < 400:
                return _tokens_from_json(payload)
            error = payload.get("error", "unknown_error") if isinstance(payload, dict) else "unknown_error"
            if error == "authorization_pending":
                if on_pending:
                    on_pending()
                continue
            if error == "slow_down":
                cur_interval += 5
                continue
            if error == "expired_token":
                raise LinkSnapAuthError("DEVICE_CODE_EXPIRED", "device code expired before approval")
            if error == "access_denied":
                raise LinkSnapAuthError("ACCESS_DENIED", "user denied authorization")
            desc = payload.get("error_description", "token request failed") if isinstance(payload, dict) else "token request failed"
            raise LinkSnapAuthError(error.upper(), str(desc))
    finally:
        if http is None:
            client.close()


def refresh_access_token(
    *,
    issuer: str,
    client_id: str,
    refresh_token: str,
    scope: Optional[str] = None,
    http: Optional[httpx.Client] = None,
) -> DeviceTokens:
    disco = fetch_discovery(issuer, http=http)
    body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if scope:
        body["scope"] = scope
    client = http or _http()
    try:
        res = client.post(
            disco.token_endpoint,
            data=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError as e:
        raise RefreshError("NETWORK_ERROR", str(e)) from e
    finally:
        if http is None:
            client.close()
    payload = _safe_json(res)
    if res.status_code >= 400:
        code = payload.get("error", "refresh_failed") if isinstance(payload, dict) else "refresh_failed"
        desc = payload.get("error_description", "refresh failed") if isinstance(payload, dict) else "refresh failed"
        raise RefreshError(str(code).upper(), str(desc))
    tokens = _tokens_from_json(payload)
    if tokens.refresh_token is None:
        tokens.refresh_token = refresh_token  # OAuth allows server to omit; reuse old
    return tokens


def _tokens_from_json(payload: Dict[str, Any]) -> DeviceTokens:
    expires_in = int(payload.get("expires_in", 3600))
    return DeviceTokens(
        access_token=payload["access_token"],
        expires_at=int(time.time()) + expires_in,
        token_type=payload.get("token_type", "Bearer"),
        refresh_token=payload.get("refresh_token"),
        scope=payload.get("scope"),
    )


def _safe_json(res: httpx.Response) -> Any:
    try:
        return res.json()
    except Exception:
        return {}
