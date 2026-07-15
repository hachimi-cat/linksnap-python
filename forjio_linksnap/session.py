"""Multi-profile credentials store mirroring `@forjio/sdk`'s Session.

INI-format ~/.linksnap/credentials, one section per profile. Single-flight
refresh guard prevents concurrent calls from burning the Huudis
refresh-token family (Huudis revokes the entire family on reuse).
"""

from __future__ import annotations

import configparser
import os
import stat
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from .device_flow import refresh_access_token
from .errors import LinkSnapAuthError, RefreshError


@dataclass
class ProfileData:
    access_token: str
    expires_at: int
    issuer: str
    client_id: str
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    account_id: Optional[str] = None


class Session:
    def __init__(
        self,
        *,
        brand: str = "linksnap",
        profile: Optional[str] = None,
        credentials_path: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self.brand = brand
        env_key = f"{brand.upper()}_PROFILE"
        self.profile = profile or os.environ.get(env_key, "default")
        self.credentials_path = Path(
            credentials_path or os.path.expanduser(f"~/.{brand}/credentials")
        )
        self.http = http
        self._data: Optional[ProfileData] = None
        self._refresh_lock = threading.Lock()
        self._refresh_in_flight: Optional[threading.Event] = None
        self._refresh_error: Optional[BaseException] = None

    @property
    def data(self) -> Optional[ProfileData]:
        return self._data

    def load(self) -> ProfileData:
        if not self.credentials_path.exists():
            raise LinkSnapAuthError(
                "SESSION_NOT_FOUND",
                f"credentials file not found at {self.credentials_path}",
            )
        parser = configparser.ConfigParser()
        parser.read(self.credentials_path)
        if not parser.has_section(self.profile):
            raise LinkSnapAuthError(
                "PROFILE_NOT_FOUND",
                f"profile [{self.profile}] not in {self.credentials_path}",
            )
        section = parser[self.profile]
        for required in ("access_token", "issuer", "client_id"):
            if required not in section:
                raise LinkSnapAuthError(
                    "SESSION_INCOMPLETE",
                    f"profile [{self.profile}] missing {required}",
                )
        self._data = ProfileData(
            access_token=section["access_token"],
            expires_at=int(section.get("expires_at", "0") or "0"),
            issuer=section["issuer"],
            client_id=section["client_id"],
            refresh_token=section.get("refresh_token") or None,
            scope=section.get("scope") or None,
            account_id=section.get("account_id") or None,
        )
        return self._data

    def save(self, data: Optional[ProfileData] = None) -> None:
        if data is not None:
            self._data = data
        if self._data is None:
            raise RuntimeError("Session.save called with no data")
        parser = configparser.ConfigParser()
        if self.credentials_path.exists():
            parser.read(self.credentials_path)
        parser[self.profile] = {
            "access_token": self._data.access_token,
            "expires_at": str(self._data.expires_at),
            "issuer": self._data.issuer,
            "client_id": self._data.client_id,
        }
        if self._data.refresh_token:
            parser[self.profile]["refresh_token"] = self._data.refresh_token
        if self._data.scope:
            parser[self.profile]["scope"] = self._data.scope
        if self._data.account_id:
            parser[self.profile]["account_id"] = self._data.account_id
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write with chmod 600.
        fd, tmp = tempfile.mkstemp(prefix=".credentials.", dir=str(self.credentials_path.parent))
        try:
            with os.fdopen(fd, "w") as f:
                parser.write(f)
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(tmp, self.credentials_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def clear(self) -> None:
        if not self.credentials_path.exists():
            self._data = None
            return
        parser = configparser.ConfigParser()
        parser.read(self.credentials_path)
        if parser.has_section(self.profile):
            parser.remove_section(self.profile)
        self._data = None
        if not parser.sections():
            self.credentials_path.unlink(missing_ok=True)
            return
        fd, tmp = tempfile.mkstemp(prefix=".credentials.", dir=str(self.credentials_path.parent))
        try:
            with os.fdopen(fd, "w") as f:
                parser.write(f)
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(tmp, self.credentials_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def is_expired(self) -> bool:
        if self._data is None:
            return True
        return time.time() >= self._data.expires_at

    def will_expire_soon(self, buffer_sec: int = 300) -> bool:
        if self._data is None:
            return True
        return time.time() + buffer_sec >= self._data.expires_at

    def refresh(self) -> None:
        """Single-flight refresh. Concurrent callers share the same refresh."""
        with self._refresh_lock:
            if self._refresh_in_flight is not None:
                event = self._refresh_in_flight
            else:
                self._refresh_in_flight = threading.Event()
                self._refresh_error = None
                event = self._refresh_in_flight
                self._spawn_refresh()
        event.wait()
        if self._refresh_error is not None:
            raise self._refresh_error

    def _spawn_refresh(self) -> None:
        # Run inline (caller is already on a thread; httpx is sync).
        try:
            self._do_refresh()
        except BaseException as e:  # noqa: BLE001
            self._refresh_error = e
        finally:
            event = self._refresh_in_flight
            with self._refresh_lock:
                self._refresh_in_flight = None
            if event is not None:
                event.set()

    def _do_refresh(self) -> None:
        if self._data is None:
            raise RefreshError("NO_SESSION", "load() before refresh()")
        if not self._data.refresh_token:
            raise RefreshError("NO_REFRESH_TOKEN", "session has no refresh_token")
        tokens = refresh_access_token(
            issuer=self._data.issuer,
            client_id=self._data.client_id,
            refresh_token=self._data.refresh_token,
            scope=self._data.scope,
            http=self.http,
        )
        self._data = ProfileData(
            access_token=tokens.access_token,
            expires_at=tokens.expires_at,
            issuer=self._data.issuer,
            client_id=self._data.client_id,
            refresh_token=tokens.refresh_token or self._data.refresh_token,
            scope=tokens.scope or self._data.scope,
            account_id=self._data.account_id,
        )
        self.save()
