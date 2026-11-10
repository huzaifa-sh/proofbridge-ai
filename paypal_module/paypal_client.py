"""
PayPal Client / Authentication Helper.

Provides a reusable, thread-safe function to authenticate against PayPal's OAuth 2.0
endpoint (/v1/oauth2/token) using Client ID and Secret. Tokens are cached in memory
and reused until 60 seconds before expiration. Automatic retries are applied only to
token fetching on network or 5xx errors (never on 4xx or payment POST operations).
"""

import threading
import time
import requests
from requests.auth import HTTPBasicAuth

try:
    from .config import get_settings
except ImportError:
    from config import get_settings

# In-memory token cache protected by a reentrant lock
_token_lock = threading.Lock()
_cached_token: str | None = None
_token_expires_at: float = 0.0


def clear_token_cache() -> None:
    """Clear the cached token in memory. Useful for tests."""
    global _cached_token, _token_expires_at
    with _token_lock:
        _cached_token = None
        _token_expires_at = 0.0


def get_access_token() -> str:
    """
    Authenticate with PayPal Sandbox using OAuth 2.0 client credentials.
    Reuses a cached token if valid (expires in > 60 seconds).
    Retries up to 3 attempts (1s, 2s delays) on network errors or HTTP 5xx.
    Does NOT retry on HTTP 4xx (fails immediately).

    Returns:
        str: A valid OAuth 2.0 Bearer access token.

    Raises:
        RuntimeError: If authentication fails.
    """
    global _cached_token, _token_expires_at

    now = time.time()
    # Fast-path read without lock
    if _cached_token and now < (_token_expires_at - 60):
        return _cached_token

    with _token_lock:
        # Double-check inside lock
        now = time.time()
        if _cached_token and now < (_token_expires_at - 60):
            return _cached_token

        settings = get_settings()
        token_url = f"{settings.base_url}/v1/oauth2/token"
        auth = HTTPBasicAuth(settings.client_id, settings.client_secret)

        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {
            "grant_type": "client_credentials"
        }

        delays = [1, 2]
        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    token_url,
                    auth=auth,
                    headers=headers,
                    data=data,
                    timeout=15
                )
            except requests.RequestException as exc:
                last_error = RuntimeError(f"Network error while connecting to PayPal Sandbox: {exc}")
                if attempt < max_attempts - 1:
                    time.sleep(delays[attempt])
                    continue
                raise last_error from exc

            # Do NOT retry on 4xx (client error / invalid credentials) - fail immediately
            if 400 <= response.status_code < 500:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error_description", error_data.get("error", response.text))
                except Exception:
                    pass
                raise RuntimeError(
                    f"PayPal authentication failed [HTTP {response.status_code}]: {error_msg}"
                )

            # Retry on 5xx (server error)
            if response.status_code >= 500:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error_description", error_data.get("error", response.text))
                except Exception:
                    pass
                last_error = RuntimeError(
                    f"PayPal authentication failed [HTTP {response.status_code}]: {error_msg}"
                )
                if attempt < max_attempts - 1:
                    time.sleep(delays[attempt])
                    continue
                raise last_error

            # Unexpected non-200 status code
            if response.status_code != 200:
                raise RuntimeError(
                    f"PayPal authentication returned unexpected status [HTTP {response.status_code}]"
                )

            # 200 OK: extract token and cache
            response_json = response.json()
            access_token = response_json.get("access_token")
            if not access_token:
                raise RuntimeError("PayPal response did not contain an 'access_token' field.")

            expires_in = response_json.get("expires_in", 32400)
            try:
                expires_in_sec = float(expires_in)
            except (ValueError, TypeError):
                expires_in_sec = 32400.0

            _cached_token = access_token
            _token_expires_at = time.time() + expires_in_sec
            return _cached_token

        if last_error:
            raise last_error
        raise RuntimeError("PayPal authentication failed after max attempts.")
