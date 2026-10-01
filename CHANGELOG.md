# Changelog

## 0.2.0
- The API key goes as `Authorization: ApiKey <key>`, which is what the LinkSnap API reads (it was sent as `Bearer`). A per-call `auth_token` that is an `lsk_…` key goes the same way; a session or access token stays `Bearer`. The key now also applies to the raw verbs (`client.api.get(...)`) and takes precedence over a `session`.
- `billing.checkout` / `billing.downgrade` send the plan as `plan`, the field the API reads (they sent `planId`).
- `client.api.*` regenerated: webhook endpoints, and every customer route, take the API key.
- A test checks every hand-written method's route against the API spec (`backend/openapi.json`).

## 0.1.2
- `client.api.<area>_<action>(...)`: every LinkSnap feature route, one method each, generated from the API spec (`scripts/apigen.sh`). Calls go through the same ApiClient and credentials as the resource methods. `client.api.get/post/patch/put/delete/paginate` keep working as before.

## 0.1.1
- Initial tracked release.
