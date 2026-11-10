"""
Offline unit tests for token caching and retry mechanism in paypal_client.py.

Runs completely offline with unittest.mock (no real network calls).
Verifies:
1. Second call reuses the cached token (1 network call total).
2. Expired token triggers a refresh (2 network calls total).
3. Two 503 errors followed by 200 OK succeeds with 3 attempts.
4. HTTP 401 fails immediately with no retry (1 attempt total).
"""

import sys
import time
from unittest.mock import MagicMock, patch

try:
    from .paypal_client import get_access_token, clear_token_cache
except ImportError:
    from paypal_client import get_access_token, clear_token_cache


def create_mock_response(status_code: int, json_data: dict, text: str = "") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.text = text or str(json_data)
    return mock_resp


def test_token_reuse():
    clear_token_cache()
    mock_resp = create_mock_response(200, {"access_token": "cached_token_abc", "expires_in": 3600})

    with patch("requests.post", return_value=mock_resp) as mock_post:
        token1 = get_access_token()
        token2 = get_access_token()

        assert token1 == "cached_token_abc", f"Expected 'cached_token_abc', got '{token1}'"
        assert token2 == "cached_token_abc", f"Expected 'cached_token_abc', got '{token2}'"
        assert mock_post.call_count == 1, f"Expected 1 POST call, got {mock_post.call_count}"
        print("  [PASS] Case 1: Second call reuses cached token (1 POST call)")


def test_token_expiry_refresh():
    clear_token_cache()
    mock_resp1 = create_mock_response(200, {"access_token": "token_initial", "expires_in": 100})
    mock_resp2 = create_mock_response(200, {"access_token": "token_refreshed", "expires_in": 3600})

    with patch("requests.post", side_effect=[mock_resp1, mock_resp2]) as mock_post:
        # First call gets initial token expiring in 100s
        token1 = get_access_token()
        assert token1 == "token_initial", f"Expected 'token_initial', got '{token1}'"

        # Simulate passage of time past (expires_in - 60s) threshold (e.g. 50s elapsed -> only 50s left < 60s)
        with patch("time.time", return_value=time.time() + 50):
            token2 = get_access_token()
            assert token2 == "token_refreshed", f"Expected 'token_refreshed', got '{token2}'"

        assert mock_post.call_count == 2, f"Expected 2 POST calls due to expiry refresh, got {mock_post.call_count}"
        print("  [PASS] Case 2: Expired token triggers refresh (2 POST calls)")


def test_retry_on_503_and_succeed():
    clear_token_cache()
    resp_503_1 = create_mock_response(503, {"error": "service_unavailable"}, "Service Unavailable")
    resp_503_2 = create_mock_response(503, {"error": "service_unavailable"}, "Service Unavailable")
    resp_200 = create_mock_response(200, {"access_token": "token_after_503_retries", "expires_in": 3600})

    with patch("requests.post", side_effect=[resp_503_1, resp_503_2, resp_200]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            token = get_access_token()
            assert token == "token_after_503_retries", f"Expected 'token_after_503_retries', got '{token}'"
            assert mock_post.call_count == 3, f"Expected 3 POST calls, got {mock_post.call_count}"
            assert mock_sleep.call_count == 2, f"Expected 2 sleep calls (1s and 2s), got {mock_sleep.call_count}"
            mock_sleep.assert_any_call(1)
            mock_sleep.assert_any_call(2)
            print("  [PASS] Case 3: Two 503s followed by success retries and succeeds (3 POST calls, delays 1s then 2s)")


def test_fail_immediately_on_401():
    clear_token_cache()
    resp_401 = create_mock_response(401, {"error": "invalid_client", "error_description": "Client Authentication failed"})

    with patch("requests.post", return_value=resp_401) as mock_post:
        with patch("time.sleep") as mock_sleep:
            failed = False
            try:
                get_access_token()
            except RuntimeError as exc:
                failed = True
                assert "HTTP 401" in str(exc), f"Expected HTTP 401 in error message, got: {exc}"

            assert failed, "Expected RuntimeError on 401 invalid_client"
            assert mock_post.call_count == 1, f"Expected exactly 1 call with NO retry on 401, got {mock_post.call_count}"
            assert mock_sleep.call_count == 0, f"Expected 0 sleep calls on 401, got {mock_sleep.call_count}"
            print("  [PASS] Case 4: 401 fails immediately with NO retry (1 POST call, 0 delays)")


def run_all_tests():
    print("=" * 65)
    print("ProofBridge AI - Running Offline Token Cache & Retry Tests")
    print("=" * 65)
    try:
        test_token_reuse()
        test_token_expiry_refresh()
        test_retry_on_503_and_succeed()
        test_fail_immediately_on_401()
        print("-" * 65)
        print("ALL TOKEN CACHE & RETRY TESTS PASSED (OFFLINE / MOCKED)!")
        print("=" * 65)
        return True
    except AssertionError as err:
        print(f"\n[FAIL] Test assertion failed: {err}")
        print("=" * 65)
        return False
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error during test: {exc}")
        print("=" * 65)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
