"""
Diagnostic script to verify PayPal Sandbox connectivity and credentials.

Usage:
    python check_connection.py

Output:
    Prints SUCCESS with the first 8 characters of the access token,
    or prints FAILURE with troubleshooting information and missing variables.
    Never prints credentials or the complete token.
"""

import sys

try:
    from .config import get_settings, get_missing_settings
    from .paypal_client import get_access_token
except ImportError:
    from config import get_settings, get_missing_settings
    from paypal_client import get_access_token


def main():
    print("=" * 60)
    print("Testing connection to PayPal Sandbox...")
    print("=" * 60)

    # 1. Check for missing configuration variables
    missing = get_missing_settings()
    if missing:
        print("\n[FAILURE] Missing required environment variables in .env:")
        for var in missing:
            print(f"  - {var}")
        print("\nTroubleshooting Tips:")
        print("1. Ensure 'paypal_module/.env' exists and matches '.env.example'.")
        print("2. Populate all missing variables with your PayPal Sandbox credentials.")
        print("=" * 60)
        sys.exit(1)

    try:
        settings = get_settings()
        print(f"Target URL: {settings.base_url}")
        print("-" * 60)

        token = get_access_token()
        # Security rule: display ONLY the first 8 characters of the token
        token_prefix = token[:8] if len(token) >= 8 else token

        print("\n[SUCCESS] Connected to PayPal Sandbox successfully!")
        print(f"Token acquired : {token_prefix}... (truncated for security)")
        print("Your credentials are valid and ready to create orders.\n")
        print("=" * 60)
        sys.exit(0)

    except Exception as exc:
        print("\n[FAILURE] Connection test failed.")
        print(f"Details : {exc}\n")
        print("Troubleshooting Tips:")
        print("1. Check that PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET have no extra spaces or quotes.")
        print("2. Ensure you are using Sandbox app credentials, not Live PayPal credentials.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
