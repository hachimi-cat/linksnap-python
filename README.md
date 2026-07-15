# linksnap (Python)

Official Python SDK for [LinkSnap](https://linksnap.forjio.com). Resource-namespaced
client for short links, QR codes, click analytics, custom domains, workspaces,
billing, and API keys — with Huudis OIDC device-flow auth and the Forjio
multi-profile credentials store.

Python parity with `@forjio/linksnap-node`.

## Install

```bash
pip install forjio-linksnap
```

## Quickstart

```python
from forjio_linksnap import LinkSnapClient

# Static API key (CI / headless):
ls = LinkSnapClient(api_key="lk_live_...")
link = ls.links.create({"url": "https://example.com/long/path", "slug": "promo"})
print(link["id"], link["slug"])

stats = ls.stats.show(link["slug"])
print(stats["totalClicks"])
ls.close()
```

## Sign in with Huudis (device flow)

```python
from forjio_linksnap import (
    LinkSnapClient,
    Session,
    start_device_flow,
    poll_device_token,
)
import webbrowser

ISSUER = "https://huudis.com"
CLIENT_ID = "oc_linksnap_cli"

# 1. Start the device flow
start = start_device_flow(issuer=ISSUER, client_id=CLIENT_ID)
print(f"Open {start.verification_uri} and enter {start.user_code}")
webbrowser.open(start.verification_uri_complete or start.verification_uri)

# 2. Poll for the user's approval
tokens = poll_device_token(
    issuer=ISSUER, client_id=CLIENT_ID, device_code=start.device_code, interval=start.interval
)

# 3. Persist the session (~/.linksnap/credentials, ini-format)
from forjio_linksnap import ProfileData
session = Session(brand="linksnap", profile="default")
session.save(
    ProfileData(
        access_token=tokens.access_token,
        expires_at=tokens.expires_at,
        issuer=ISSUER,
        client_id=CLIENT_ID,
        refresh_token=tokens.refresh_token,
        scope=tokens.scope,
    )
)

# 4. Build a client backed by the session — auto-refreshes on expiry
ls = LinkSnapClient(session=session)
me = ls.account.me()
print(me)
```

## Resource surface

| Namespace | Methods |
|---|---|
| `client.links` | `list`, `get`, `create`, `update`, `delete`, `bulk`, `export`, `import_csv` |
| `client.stats` | `show`, `export`, `workspace` |
| `client.qr` | `list`, `get`, `create`, `delete`, `download`, `stats` |
| `client.tags` | `list` |
| `client.domains` | `list`, `add`, `verify`, `remove` |
| `client.billing` | `plans`, `plan`, `subscription`, `usage`, `history`, `invoices`, `checkout`, `cancel`, `downgrade` |
| `client.workspace` | `show`, `rename`, `members.list`, `members.add`, `members.remove` |
| `client.api_keys` | `list`, `create`, `delete` |
| `client.account` | `me`, `update`, `change_password`, `delete` |
| `client.health()` | unauthenticated health probe |

Every method accepts an optional `auth_token=` keyword to override the
client-level bearer for a single call (same shape as the Node SDK's
`(args, authToken?)` calling convention).

## Errors

```python
from forjio_linksnap import LinkSnapError

try:
    ls.links.create({})
except LinkSnapError as e:
    print(e.code, e.message, e.status, e.request_id)
```

`LinkSnapError` carries `.code` / `.message` / `.status` / `.request_id`
/ `.details` — parity with the Node SDK's `LinkSnapError` (= `@forjio/sdk`
`ApiError`).

## Source

<https://github.com/hachimi-cat/linksnap-python>

## License

MIT
