"""
Offline unit tests for payment state mapping (derive_payment_state).

Tests normalize PayPal order response payloads into standard ProofBridge AI states:
- PENDING_APPROVAL
- APPROVED
- HELD
- PAID
- VOIDED
Runs completely offline with no network access.
"""

import sys

try:
    from .payments import derive_payment_state
except ImportError:
    from payments import derive_payment_state


# Sample Order Dictionaries conforming to PayPal Orders API v2
SAMPLE_CREATED_ORDER = {
    "id": "5O190127TN364715T",
    "status": "CREATED",
    "intent": "CAPTURE",
    "purchase_units": [
        {
            "reference_id": "CASE-001",
            "amount": {"currency_code": "USD", "value": "100.00"},
        }
    ],
}

SAMPLE_APPROVED_ORDER = {
    "id": "5O190127TN364715T",
    "status": "APPROVED",
    "intent": "CAPTURE",
    "purchase_units": [
        {
            "reference_id": "CASE-002",
            "amount": {"currency_code": "USD", "value": "100.00"},
        }
    ],
    "payer": {
        "email_address": "buyer@example.com",
        "payer_id": "BUYER123"
    },
}

SAMPLE_AUTHORIZED_AND_HELD_ORDER = {
    "id": "5O190127TN364715T",
    "status": "COMPLETED",
    "intent": "AUTHORIZE",
    "purchase_units": [
        {
            "reference_id": "CASE-003",
            "amount": {"currency_code": "USD", "value": "100.00"},
            "payments": {
                "authorizations": [
                    {
                        "id": "87349102US839201A",
                        "status": "CREATED",
                        "amount": {"currency_code": "USD", "value": "100.00"},
                    }
                ]
            },
        }
    ],
}

SAMPLE_AUTHORIZED_THEN_CAPTURED_ORDER = {
    "id": "5O190127TN364715T",
    "status": "COMPLETED",
    "intent": "AUTHORIZE",
    "purchase_units": [
        {
            "reference_id": "CASE-004",
            "amount": {"currency_code": "USD", "value": "100.00"},
            "payments": {
                "authorizations": [
                    {
                        "id": "87349102US839201A",
                        "status": "CAPTURED",
                        "amount": {"currency_code": "USD", "value": "100.00"},
                    }
                ],
                "captures": [
                    {
                        "id": "7AB12345CD67890",
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "100.00"},
                    }
                ],
            },
        }
    ],
}

SAMPLE_AUTHORIZED_THEN_VOIDED_ORDER = {
    "id": "5O190127TN364715T",
    "status": "COMPLETED",
    "intent": "AUTHORIZE",
    "purchase_units": [
        {
            "reference_id": "CASE-005",
            "amount": {"currency_code": "USD", "value": "100.00"},
            "payments": {
                "authorizations": [
                    {
                        "id": "87349102US839201A",
                        "status": "VOIDED",
                        "amount": {"currency_code": "USD", "value": "100.00"},
                    }
                ]
            },
        }
    ],
}

SAMPLE_DIRECT_CAPTURE_COMPLETED_ORDER = {
    "id": "5O190127TN364715T",
    "status": "COMPLETED",
    "intent": "CAPTURE",
    "purchase_units": [
        {
            "reference_id": "CASE-006",
            "amount": {"currency_code": "USD", "value": "100.00"},
            "payments": {
                "captures": [
                    {
                        "id": "7AB12345CD67890",
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "100.00"},
                    }
                ]
            },
        }
    ],
}


def test_cases():
    test_suite = [
        ("created", SAMPLE_CREATED_ORDER, "PENDING_APPROVAL"),
        ("approved", SAMPLE_APPROVED_ORDER, "APPROVED"),
        ("authorized-and-held", SAMPLE_AUTHORIZED_AND_HELD_ORDER, "HELD"),
        ("authorized-then-captured", SAMPLE_AUTHORIZED_THEN_CAPTURED_ORDER, "PAID"),
        ("authorized-then-voided", SAMPLE_AUTHORIZED_THEN_VOIDED_ORDER, "VOIDED"),
        ("direct-capture-completed", SAMPLE_DIRECT_CAPTURE_COMPLETED_ORDER, "PAID"),
    ]

    print("=" * 65)
    print("ProofBridge AI - Running Offline State Mapping Tests")
    print("=" * 65)

    all_passed = True

    for name, payload, expected in test_suite:
        actual = derive_payment_state(payload)
        if actual == expected:
            print(f"  [PASS] {name:<26} -> {actual}")
        else:
            print(f"  [FAIL] {name:<26} -> Expected: {expected}, Got: {actual}")
            all_passed = False

    print("-" * 65)
    if all_passed:
        print("ALL STATE MAPPING TESTS PASSED (OFFLINE / NO NETWORK)!")
    else:
        print("SOME TESTS FAILED.")
    print("=" * 65)

    return all_passed


if __name__ == "__main__":
    passed = test_cases()
    sys.exit(0 if passed else 1)
