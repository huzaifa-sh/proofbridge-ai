"""
Test script to create a PayPal Sandbox order for ProofBridge AI.

Usage:
    python test_create_order.py

Calls:
    create_payment("100.00", "USD", "CASE-001", mode="capture")

Output:
    Displays order_id, status, and buyer approval_link.
    Safely prints HTTP status code and error messages on failure,
    never leaking tokens, headers, or client secrets.
"""

import sys

try:
    from .payments import create_payment
except ImportError:
    from payments import create_payment


def main():
    print("=" * 65)
    print("ProofBridge AI - Testing Order Creation (create_payment)")
    print("=" * 65)
    print("Parameters:")
    print("  Amount   : 100.00")
    print("  Currency : USD")
    print("  Case ID  : CASE-001")
    print("  Mode     : capture (intent=CAPTURE)")
    print("-" * 65)

    try:
        result = create_payment(
            amount="100.00",
            currency="USD",
            case_id="CASE-001",
            mode="capture"
        )

        order_id = result.get("order_id")
        status = result.get("status")
        payment_state = result.get("payment_state")
        approval_link = result.get("approval_link")

        print("\n[SUCCESS] Order Created Successfully in PayPal Sandbox!\n")
        print(f"  Order ID      : {order_id}")
        print(f"  Status        : {status}")
        if payment_state:
            print(f"  Payment State : {payment_state}")
        print(f"  Approval Link : {approval_link}")
        print("\n" + "-" * 65)
        print("NEXT STEPS:")
        print("1. Copy the Approval Link above and open it in your browser.")
        print("2. Log in using your PayPal Sandbox Personal (Buyer) account.")
        print("3. Click 'Complete Purchase' / 'Agree and Continue' to approve the order.")
        print(f"4. Then run: python test_capture.py {order_id}")
        print("=" * 65)
        sys.exit(0)

    except Exception as exc:
        print("\n[FAILURE] Order creation failed.")
        # Print readable error message without leaking headers, tokens, or secrets
        print(f"  Details: {exc}")
        print("=" * 65)
        sys.exit(1)


if __name__ == "__main__":
    main()
