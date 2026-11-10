"""
Interactive CLI test script for PayPal Hold-and-Capture Lifecycle.

Usage:
    Step 1 (Create Hold Order):
        python test_hold_flow.py create

    Step 2 (Authorize Funds after Buyer Approval):
        python test_hold_flow.py authorize <ORDER_ID>

    Step 3A (Capture Authorized Hold):
        python test_hold_flow.py capture <AUTH_ID>

    Step 3B (OR Void / Cancel Authorized Hold):
        python test_hold_flow.py void <AUTH_ID>
"""

import sys

try:
    from .payments import (
        create_payment,
        authorize_payment,
        capture_authorization,
        void_authorization,
    )
except ImportError:
    from payments import (
        create_payment,
        authorize_payment,
        capture_authorization,
        void_authorization,
    )


def print_usage():
    print("=" * 65)
    print("ProofBridge AI - PayPal Hold Flow Test CLI")
    print("=" * 65)
    print("Usage:")
    print("  python test_hold_flow.py create")
    print("  python test_hold_flow.py authorize <ORDER_ID>")
    print("  python test_hold_flow.py capture <AUTH_ID>")
    print("  python test_hold_flow.py void <AUTH_ID>")
    print("=" * 65)


def handle_create():
    print("=" * 65)
    print("Step 1: Creating Order with mode='authorize' (intent=AUTHORIZE)...")
    print("=" * 65)
    try:
        result = create_payment(
            amount="100.00",
            currency="USD",
            case_id="CASE-HOLD-001",
            mode="authorize"
        )
        order_id = result.get("order_id")
        status = result.get("status")
        payment_state = result.get("payment_state")
        approval_link = result.get("approval_link")

        print("\n[SUCCESS] Hold Order Created Successfully in PayPal Sandbox!\n")
        print(f"  Order ID      : {order_id}")
        print(f"  Status        : {status}")
        if payment_state:
            print(f"  Payment State : {payment_state}")
        print(f"  Approval Link : {approval_link}")
        print("\n" + "-" * 65)
        print("NEXT STEPS:")
        print("1. Open the Approval Link above in your browser and approve the hold.")
        print(f"2. Then run: python test_hold_flow.py authorize {order_id}")
        print("=" * 65)
        sys.exit(0)
    except Exception as exc:
        print("\n[FAILURE] Order creation failed.")
        print(f"  Details: {exc}")
        print("=" * 65)
        sys.exit(1)


def handle_authorize(order_id: str):
    print("=" * 65)
    print(f"Step 2: Authorizing Hold on Order {order_id}...")
    print("=" * 65)
    try:
        result = authorize_payment(order_id)
        auth_id = result.get("authorization_id")
        auth_status = result.get("authorization_status")
        status = result.get("status")
        payment_state = result.get("payment_state")
        amount = result.get("amount")
        currency = result.get("currency")

        print("\n[SUCCESS] Order Authorized Successfully!\n")
        print(f"  Order ID             : {result.get('order_id')}")
        print(f"  Authorization ID     : {auth_id}")
        print(f"  Status               : {status}")
        print(f"  Payment State        : {payment_state}")
        print(f"  Authorization Status : {auth_status}")
        print(f"  Held Amount          : {amount} {currency}")
        print("\n" + "-" * 65)
        print("NEXT STEPS:")
        print("You can now either capture the funds or void (release) the hold:")
        print(f"  To Capture: python test_hold_flow.py capture {auth_id}")
        print(f"  To Void:    python test_hold_flow.py void {auth_id}")
        print("=" * 65)
        sys.exit(0)
    except Exception as exc:
        print("\n[FAILURE] Authorization failed.")
        print(f"  Details: {exc}")
        print("=" * 65)
        sys.exit(1)


def handle_capture(auth_id: str):
    print("=" * 65)
    print(f"Step 3A: Capturing Authorization Hold {auth_id}...")
    print("=" * 65)
    try:
        result = capture_authorization(auth_id)
        print("\n[SUCCESS] Funds Captured Successfully from Authorization Hold!\n")
        print(f"  Authorization ID : {result.get('authorization_id')}")
        if result.get('capture_id'):
            print(f"  Capture ID       : {result.get('capture_id')}")
        print(f"  Status           : {result.get('status')}")
        print(f"  Payment State    : {result.get('payment_state')}")
        print(f"  Captured Amount  : {result.get('amount')}")
        print(f"  Currency         : {result.get('currency')}")
        print("=" * 65)
        sys.exit(0)
    except Exception as exc:
        print("\n[FAILURE] Capture authorization failed.")
        print(f"  Details: {exc}")
        print("=" * 65)
        sys.exit(1)


def handle_void(auth_id: str):
    print("=" * 65)
    print(f"Step 3B: Voiding Authorization Hold {auth_id}...")
    print("=" * 65)
    try:
        result = void_authorization(auth_id)
        print("\n[SUCCESS] Authorization Hold Voided Successfully!\n")
        print(f"  Authorization ID : {result.get('authorization_id')}")
        print(f"  Status           : {result.get('status')}")
        print(f"  Payment State    : {result.get('payment_state')}")
        print("  Funds have been released back to the buyer.")
        print("=" * 65)
        sys.exit(0)
    except Exception as exc:
        print("\n[FAILURE] Void authorization failed.")
        print(f"  Details: {exc}")
        print("=" * 65)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower().strip()

    if command == "create":
        handle_create()
    elif command == "authorize":
        if len(sys.argv) < 3 or not sys.argv[2].strip():
            print("[ERROR] Missing required <ORDER_ID>")
            print("Usage: python test_hold_flow.py authorize <ORDER_ID>")
            sys.exit(1)
        handle_authorize(sys.argv[2].strip())
    elif command == "capture":
        if len(sys.argv) < 3 or not sys.argv[2].strip():
            print("[ERROR] Missing required <AUTH_ID>")
            print("Usage: python test_hold_flow.py capture <AUTH_ID>")
            sys.exit(1)
        handle_capture(sys.argv[2].strip())
    elif command == "void":
        if len(sys.argv) < 3 or not sys.argv[2].strip():
            print("[ERROR] Missing required <AUTH_ID>")
            print("Usage: python test_hold_flow.py void <AUTH_ID>")
            sys.exit(1)
        handle_void(sys.argv[2].strip())
    else:
        print(f"[ERROR] Unknown command: '{command}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
