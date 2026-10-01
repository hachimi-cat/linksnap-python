"""Official Python SDK for LinkSnap.

Mirrors the surface of `@forjio/linksnap-node`:

- `LinkSnapClient` with resource namespaces (links, stats, qr, tags,
  domains, billing, workspace, api_keys, account, plus `health()`).
- OIDC device authorization grant (RFC 8628) for CLI sign-in via Huudis.
- Multi-profile `Session` for `~/.linksnap/credentials`.
- `ApiClient` with proactive + reactive token refresh and Forjio envelope
  unwrap.
"""

from .client import LinkSnapClient
from .device_flow import (
    DeviceFlowStart,
    DeviceTokens,
    DiscoveryDocument,
    clear_discovery_cache,
    fetch_discovery,
    poll_device_token,
    refresh_access_token,
    start_device_flow,
)
from .errors import (
    ApiError,
    LinkSnapAuthError,
    LinkSnapError,
    NetworkError,
    RefreshError,
)
from .http_client import ApiClient
from .session import ProfileData, Session

__all__ = [
    # client
    "LinkSnapClient",
    # device flow
    "DeviceFlowStart",
    "DeviceTokens",
    "DiscoveryDocument",
    "clear_discovery_cache",
    "fetch_discovery",
    "poll_device_token",
    "refresh_access_token",
    "start_device_flow",
    # errors
    "ApiError",
    "LinkSnapAuthError",
    "LinkSnapError",
    "NetworkError",
    "RefreshError",
    # http client
    "ApiClient",
    # session
    "ProfileData",
    "Session",
]

__version__ = "0.4.0"
