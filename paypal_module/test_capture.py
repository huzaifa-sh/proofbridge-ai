"""
Test script to capture an approved PayPal Sandbox order for ProofBridge AI.

Usage:
    python test_capture.py <ORDER_ID>

Example:
    python test_capture.py 5O190127TN364715T

Calls:
    1. capture_payment(order_id)
    2. get_payment_details(order_id)

Output:
    Displays status, amount, currency, and payer email in readable form.
    Never prints headers, access tokens, or secrets on failure.
"""

import sys

try:
    from .payments import capture_payment, get_payment_details
except ImportError:
    from payments import capture_payment, get_payment_details


def main():
    print("=" * 65)
    print("ProofBridge AI - Testing Order Capture (capture_payment)")
    print("=" * 65)

    # 1. Validate that an order_id was provided as a command-line argument
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("[ERROR] Missing required argument: <ORDER_ID>")
        print("\nUsage:")
        print("  python test_capture.py <ORDER_ID>")
        print("\nExample:")
        print("  python test_capture.py 5O190127TN364715T")
        print("=" * 65)
        sys.exit(1)

    order_id = sys.argv[1].strip()
    print(f"Target Order ID: {order_id}")
    print("-" * 65)

    try:
        # 2. Call capture_payment to collect the funds from the approved order
        print("1. Calling capture_payment()...")
        capture_result = capture_payment(order_id)

        # 3. Call get_payment_details to retrieve final order state and buyer details
        print("2. Calling get_payment_details()...")
        details = get_payment_details(order_id)

        status = details.get("status") or capture_result.get("status")
        payment_state = details.get("payment_state") or capture_result.get("payment_state")
        amount = capture_result.get("amount") or details.get("amount")
        currency = capture_result.get("currency") or details.get("currency")
        payer_email = details.get("payer_email") or "Not provided by sandbox"
        capture_id = capture_result.get("capture_id")

        print("\n[SUCCESS] Order Captured and Verified Successfully!\n")
        print(f"  Order ID      : {order_id}")
        print(f"  Status        : {status}")
        print(f"  Payment State : {payment_state}")
        print(f"  Capture ID    : {capture_id}")
        print(f"  Amount        : {amount}")
        print(f"  Currency      : {currency}")
        print(f"  Payer Email   : {payer_email}")
        print(f"  Case ID       : {details.get('case_id')}")
        print("=" * 65)
        sys.exit(0)

    except Exception as exc:
        print("\n[FAILURE] Order capture failed.")
        # Safe error reporting: output readable error without exposing headers or secrets
        print(f"  Details: {exc}")
        print("=" * 65)
        sys.exit(1)


if __name__ == "__main__":
    main()
