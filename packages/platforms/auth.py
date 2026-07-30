from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OAuthTransport(Protocol):
    def request_form(self, url: str, values: dict[str, str]) -> dict[str, Any]: ...


class UrllibOAuthTransport:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def request_form(self, url: str, values: dict[str, str]) -> dict[str, Any]:
        request = Request(url, data=urlencode(values).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - endpoint is provider configuration
            import json
            return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class OAuthState:
    value: str
    created_at: float


class OAuthStateStore:
    """Short-lived, one-time OAuth state values; tokens are never stored here."""

    def __init__(self, ttl_seconds: int = 600) -> None:
        if ttl_seconds < 60:
            raise ValueError("OAuth state TTL is too short")
        self.ttl_seconds = ttl_seconds
        self._states: dict[str, OAuthState] = {}

    def issue(self) -> str:
        value = secrets.token_urlsafe(32)
        self._states[value] = OAuthState(value, time.time())
        self._purge()
        return value

    def consume(self, value: str) -> bool:
        self._purge()
        state = self._states.pop(value, None)
        return state is not None

    def _purge(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        self._states = {key: state for key, state in self._states.items() if state.created_at >= cutoff}


@dataclass(frozen=True)
class OAuthProvider:
    provider_id: str
    authorization_endpoint: str
    token_endpoint: str
    client_id: str
    client_secret: str
    scopes: tuple[str, ...]
    revoke_endpoint: str | None = None

    def __post_init__(self) -> None:
        if not self.authorization_endpoint.startswith("https://") or not self.token_endpoint.startswith("https://"):
            raise ValueError("OAuth endpoints must use HTTPS")
        if self.revoke_endpoint is not None and not self.revoke_endpoint.startswith("https://"):
            raise ValueError("OAuth revoke endpoint must use HTTPS")
        if not self.client_id or not self.client_secret or not self.scopes:
            raise ValueError("OAuth provider credentials and scopes are required")


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    token_type: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: tuple[str, ...] = ()
    issued_at: float = 0.0

    def expired(self, *, now: float | None = None, leeway_seconds: int = 60) -> bool:
        return self.expires_in is not None and (now if now is not None else time.time()) >= self.issued_at + self.expires_in - leeway_seconds


class TokenStore(Protocol):
    def load(self, provider_id: str) -> OAuthToken | None: ...
    def save(self, provider_id: str, token: OAuthToken) -> None: ...
    def delete(self, provider_id: str) -> None: ...


class InMemoryTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, OAuthToken] = {}

    def load(self, provider_id: str) -> OAuthToken | None:
        return self._tokens.get(provider_id)

    def save(self, provider_id: str, token: OAuthToken) -> None:
        self._tokens[provider_id] = token

    def delete(self, provider_id: str) -> None:
        self._tokens.pop(provider_id, None)


class EncryptedFileTokenStore:
    """Opt-in Fernet-backed token store; callers must provide the encryption key."""

    def __init__(self, path: str | Path, encryption_key: str | bytes) -> None:
        try:
            from cryptography.fernet import Fernet
        except ImportError as error:  # pragma: no cover - depends on deployment extra
            raise RuntimeError("encrypted token storage requires the cryptography package") from error
        self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.chmod(0o600)

    def _read(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self._fernet.decrypt(self.path.read_bytes()).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            raise ValueError("encrypted OAuth token store is invalid")
        if not isinstance(value, dict):
            raise ValueError("encrypted OAuth token store must contain an object")
        return value

    def _write(self, value: dict[str, dict[str, object]]) -> None:
        payload = self._fernet.encrypt(json.dumps(value, separators=(",", ":")).encode("utf-8"))
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_bytes(payload)
        temporary.chmod(0o600)
        temporary.replace(self.path)
        self.path.chmod(0o600)

    def load(self, provider_id: str) -> OAuthToken | None:
        raw = self._read().get(provider_id)
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("stored OAuth token is invalid")
        return OAuthToken(str(raw["access_token"]), str(raw["token_type"]), raw.get("expires_in") if isinstance(raw.get("expires_in"), int) else None,
                          str(raw["refresh_token"]) if raw.get("refresh_token") is not None else None,
                          tuple(str(item) for item in raw.get("scope", [])), float(raw.get("issued_at", 0.0)))

    def save(self, provider_id: str, token: OAuthToken) -> None:
        values = self._read()
        values[provider_id] = {"access_token": token.access_token, "token_type": token.token_type, "expires_in": token.expires_in,
                               "refresh_token": token.refresh_token, "scope": list(token.scope), "issued_at": token.issued_at}
        self._write(values)

    def delete(self, provider_id: str) -> None:
        values = self._read()
        values.pop(provider_id, None)
        self._write(values)


class OAuthClient:
    def __init__(self, provider: OAuthProvider, transport: OAuthTransport | None = None) -> None:
        self.provider = provider
        self.transport = transport or UrllibOAuthTransport()

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        if not (redirect_uri.startswith("https://") or redirect_uri.startswith("http://127.0.0.1") or redirect_uri.startswith("http://localhost")):
            raise ValueError("OAuth redirect URI must use HTTPS or loopback")
        return self.provider.authorization_endpoint + "?" + urlencode({
            "client_id": self.provider.client_id, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": " ".join(self.provider.scopes), "state": state,
            "access_type": "offline" if self.provider.provider_id == "youtube" else "", "prompt": "consent" if self.provider.provider_id == "youtube" else "",
        })

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthToken:
        if not code.strip():
            raise ValueError("authorization code is empty")
        payload = self.transport.request_form(self.provider.token_endpoint, {
            "code": code, "client_id": self.provider.client_id, "client_secret": self.provider.client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        })
        return self._token(payload)

    def refresh(self, refresh_token: str) -> OAuthToken:
        if not refresh_token.strip():
            raise ValueError("refresh token is empty")
        payload = self.transport.request_form(self.provider.token_endpoint, {
            "refresh_token": refresh_token, "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret, "grant_type": "refresh_token",
        })
        token = self._token(payload)
        return OAuthToken(token.access_token, token.token_type, token.expires_in, token.refresh_token or refresh_token, token.scope, token.issued_at)

    def revoke(self, token: str) -> None:
        if self.provider.revoke_endpoint is None:
            raise ValueError("OAuth provider does not define token revocation")
        self.transport.request_form(self.provider.revoke_endpoint, {"token": token})

    @staticmethod
    def _token(payload: dict[str, Any]) -> OAuthToken:
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("OAuth response did not contain an access token")
        expires_in = payload.get("expires_in")
        if expires_in is not None and (not isinstance(expires_in, int) or expires_in <= 0):
            raise ValueError("OAuth expires_in is invalid")
        scope = payload.get("scope", ())
        if isinstance(scope, str):
            scope = tuple(scope.split())
        if not isinstance(scope, (list, tuple)) or any(not isinstance(item, str) for item in scope):
            raise ValueError("OAuth scope is invalid")
        return OAuthToken(access_token, str(payload.get("token_type", "Bearer")), expires_in, payload.get("refresh_token"), tuple(scope), time.time())


class OAuthFlowManager:
    """Binds one-time state to a provider and callback, keeping tokens in process memory only."""

    def __init__(self, clients: dict[str, OAuthClient], state_store: OAuthStateStore | None = None, token_store: TokenStore | None = None) -> None:
        self.clients = dict(clients)
        self.state_store = state_store or OAuthStateStore()
        self.token_store = token_store or InMemoryTokenStore()
        self._pending: dict[str, tuple[str, str]] = {}

    def begin(self, provider_id: str, redirect_uri: str) -> str:
        client = self.clients[provider_id]
        state = self.state_store.issue()
        self._pending[state] = (provider_id, redirect_uri)
        return client.authorization_url(redirect_uri, state)

    def complete(self, provider_id: str, code: str, state: str, redirect_uri: str) -> OAuthToken:
        if not self.state_store.consume(state):
            raise ValueError("OAuth state is invalid or expired")
        pending = self._pending.pop(state, None)
        if pending is None or pending != (provider_id, redirect_uri):
            raise ValueError("OAuth callback does not match the pending authorization")
        token = self.clients[provider_id].exchange_code(code, redirect_uri)
        self.token_store.save(provider_id, token)
        return token

    def load(self, provider_id: str) -> OAuthToken | None:
        return self.token_store.load(provider_id)

    def refresh(self, provider_id: str) -> OAuthToken:
        token = self.token_store.load(provider_id)
        if token is None or not token.refresh_token:
            raise ValueError("no refresh token is stored for provider")
        refreshed = self.clients[provider_id].refresh(token.refresh_token)
        self.token_store.save(provider_id, refreshed)
        return refreshed

    def revoke(self, provider_id: str) -> None:
        token = self.token_store.load(provider_id)
        if token is None:
            raise ValueError("provider is not authorized")
        self.clients[provider_id].revoke(token.access_token)
        self.token_store.delete(provider_id)
