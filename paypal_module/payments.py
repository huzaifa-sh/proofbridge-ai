"""
Payment operations for the ProofBridge AI PayPal integration.

Implements order creation, capture, authorization, and lifecycle management
using direct PayPal REST API v2 calls with requests.
"""

import requests

try:
    from .config import get_settings
    from .paypal_client import get_access_token
except ImportError:
    from config import get_settings
    from paypal_client import get_access_token


def derive_payment_state(data: dict) -> str:
    """
    Derive a normalized payment state from PayPal order or payment response data.

    Values:
    - PENDING_APPROVAL: Order created or requires buyer approval.
    - APPROVED: Buyer approved the payment/hold, awaiting capture or authorization.
    - HELD: Funds are successfully authorized and on hold (intent=AUTHORIZE).
    - PAID: Funds have been successfully captured and received.
    - VOIDED: Authorization hold has been voided/canceled.
    - EXPIRED: Authorization hold expired without capture.
    - FAILED: Transaction failed, declined, or was denied.
    """
    status = str(data.get("status", "")).upper()

    # 1. Direct Capture response object (from Payments v2 capture-authorization)
    if "seller_receivable_breakdown" in data or "final_capture" in data:
        if status == "COMPLETED":
            return "PAID"
        if status in ("DECLINED", "FAILED"):
            return "FAILED"

    # 2. Direct Authorization response object (from Payments v2 void or lookup)
    if "expiration_time" in data and "purchase_units" not in data:
        if status == "CREATED":
            return "HELD"
        if status == "CAPTURED":
            return "PAID"
        if status == "VOIDED":
            return "VOIDED"
        if status == "EXPIRED":
            return "EXPIRED"
        if status in ("DENIED", "FAILED"):
            return "FAILED"

    # 3. Order response object (from Orders v2)
    intent = str(data.get("intent", "")).upper()
    purchase_units = data.get("purchase_units") or [{}]
    pu = purchase_units[0] if isinstance(purchase_units, list) and purchase_units else {}
    payments = pu.get("payments", {}) if isinstance(pu, dict) else {}

    # Check captures list: if any capture is completed, money has moved
    captures = payments.get("captures", [])
    if captures and isinstance(captures, list):
        first_cap_status = str(captures[0].get("status", "")).upper()
        if first_cap_status == "COMPLETED":
            return "PAID"
        if first_cap_status in ("DECLINED", "FAILED"):
            return "FAILED"

    # For intent AUTHORIZE, check authorizations status specifically
    authorizations = payments.get("authorizations", [])
    if authorizations and isinstance(authorizations, list):
        first_auth_status = str(authorizations[0].get("status", "")).upper()
        if first_auth_status == "CREATED":
            return "HELD"
        if first_auth_status == "CAPTURED":
            return "PAID"
        if first_auth_status == "VOIDED":
            return "VOIDED"
        if first_auth_status == "EXPIRED":
            return "EXPIRED"
        if first_auth_status in ("DENIED", "FAILED"):
            return "FAILED"

    # Fall back to order-level status
    if status in ("CREATED", "SAVED", "PAYER_ACTION_REQUIRED"):
        return "PENDING_APPROVAL"
    if status == "APPROVED":
        return "APPROVED"
    if status == "COMPLETED":
        # COMPLETED on CAPTURE intent means money moved; on AUTHORIZE intent it means authorized
        if intent == "CAPTURE":
            return "PAID"
        return "HELD"
    if status == "VOIDED":
        return "VOIDED"

    return "FAILED"


def create_payment(
    amount: str,
    currency: str,
    case_id: str,
    mode: str = "capture"
) -> dict:
    """
    Create a new PayPal order using the Orders API v2.

    Args:
        amount (str): The payment amount as a string (e.g. "150.00").
        currency (str): Three-letter ISO currency code (e.g. "USD").
        case_id (str): ProofBridge AI internal dispute case identifier.
        mode (str): Payment mode: "capture" (default) or "authorize".

    Returns:
        dict: {"order_id": ..., "status": ..., "approval_link": ...}
    """
    normalized_mode = mode.lower().strip()
    if normalized_mode == "capture":
        intent = "CAPTURE"
    elif normalized_mode == "authorize":
        intent = "AUTHORIZE"
    else:
        raise ValueError(
            f"Invalid mode '{mode}'. Supported modes are 'capture' or 'authorize'."
        )

    settings = get_settings()
    access_token = get_access_token()

    payload = {
        "intent": intent,
        "purchase_units": [
            {
                "reference_id": str(case_id),
                "amount": {
                    "currency_code": currency.upper().strip(),
                    "value": str(amount),
                },
            }
        ],
    }

    # Attach optional frontend return and cancel redirect URLs if configured
    if settings.return_url or settings.cancel_url:
        experience_context = {}
        if settings.return_url:
            experience_context["return_url"] = settings.return_url
        if settings.cancel_url:
            experience_context["cancel_url"] = settings.cancel_url
        payload["payment_source"] = {
            "paypal": {
                "experience_context": experience_context
            }
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    orders_endpoint = f"{settings.base_url}/v2/checkout/orders"

    try:
        response = requests.post(
            orders_endpoint,
            headers=headers,
            json=payload,
            timeout=15
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error when calling PayPal Orders API: {exc}") from exc

    if response.status_code not in (200, 201):
        error_details = response.text
        try:
            error_json = response.json()
            error_details = error_json.get("message", response.text)
        except Exception:
            pass
        raise RuntimeError(
            f"PayPal order creation failed [HTTP {response.status_code}]: {error_details}"
        )

    data = response.json()

    order_id = data.get("id")
    status = data.get("status")

    approval_link = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approval_link = link.get("href")
            break

    return {
        "order_id": order_id,
        "status": status,
        "payment_state": derive_payment_state(data),
        "approval_link": approval_link,
    }


def get_payment_details(order_id: str) -> dict:
    """
    Fetch the latest details and normalized status of an existing PayPal order.

    Returns:
        dict: payment details including order_id, status, payment_state, intent,
              case_id, amount, currency, payer_email, authorization_id,
              authorization_status, and capture_id.
    """
    if not order_id or not str(order_id).strip():
        raise ValueError("A valid order_id must be provided.")

    settings = get_settings()
    access_token = get_access_token()
    endpoint = f"{settings.base_url}/v2/checkout/orders/{str(order_id).strip()}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error while fetching order details: {exc}") from exc

    if response.status_code != 200:
        error_msg = response.text
        try:
            error_msg = response.json().get("message", response.text)
        except Exception:
            pass
        raise RuntimeError(
            f"Failed to fetch order details for '{order_id}' [HTTP {response.status_code}]: {error_msg}"
        )

    data = response.json()
    purchase_unit = data.get("purchase_units", [{}])[0]
    amount_info = purchase_unit.get("amount", {})
    payer_info = data.get("payer", {})
    payer_email = payer_info.get("email_address")

    payments = purchase_unit.get("payments", {})
    authorizations = payments.get("authorizations", [])
    captures = payments.get("captures", [])

    auth_id = authorizations[0].get("id") if authorizations else None
    auth_status = authorizations[0].get("status") if authorizations else None
    cap_id = captures[0].get("id") if captures else None

    approval_link = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approval_link = link.get("href")
            break

    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "payment_state": derive_payment_state(data),
        "intent": data.get("intent"),
        "case_id": purchase_unit.get("reference_id"),
        "amount": amount_info.get("value"),
        "currency": amount_info.get("currency_code"),
        "approval_link": approval_link,
        "payer_email": payer_email,
        "authorization_id": auth_id,
        "authorization_status": auth_status,
        "capture_id": cap_id,
    }


def capture_payment(order_id: str) -> dict:
    """
    Capture payment for an approved order whose intent was CAPTURE.
    Repeat-safe: if order is already captured, returns current order details.
    """
    if not order_id or not str(order_id).strip():
        raise ValueError("A valid order_id must be provided.")

    settings = get_settings()
    access_token = get_access_token()
    clean_id = str(order_id).strip()
    endpoint = f"{settings.base_url}/v2/checkout/orders/{clean_id}/capture"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    try:
        response = requests.post(endpoint, headers=headers, json={}, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error while capturing order: {exc}") from exc

    if response.status_code not in (200, 201):
        error_msg = response.text
        try:
            error_json = response.json()
            error_name = str(error_json.get("name", "")).upper()
            details = error_json.get("details", [])
            issues = [str(d.get("issue", "")).upper() for d in details if isinstance(d, dict)]
            
            # Repeat-safe check: return current details if already captured
            if (
                error_name == "ORDER_ALREADY_CAPTURED"
                or "ORDER_ALREADY_CAPTURED" in issues
                or "already captured" in error_msg.lower()
            ):
                return get_payment_details(clean_id)

            if details and isinstance(details, list) and "description" in details[0]:
                error_msg = f"{error_json.get('message', '')}: {details[0]['description']}"
            else:
                error_msg = error_json.get("message", response.text)
        except Exception:
            pass

        raise RuntimeError(
            f"Failed to capture order '{clean_id}' [HTTP {response.status_code}]: {error_msg}"
        )

    data = response.json()

    capture_id = None
    amount = None
    currency = None
    try:
        captures = data["purchase_units"][0]["payments"]["captures"]
        if captures:
            first_capture = captures[0]
            capture_id = first_capture.get("id")
            amount = first_capture.get("amount", {}).get("value")
            currency = first_capture.get("amount", {}).get("currency_code")
    except (KeyError, IndexError, TypeError):
        pass

    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "payment_state": derive_payment_state(data),
        "capture_id": capture_id,
        "amount": amount,
        "currency": currency,
    }


def authorize_payment(order_id: str) -> dict:
    """
    Authorize funds for an approved order whose intent was AUTHORIZE.
    Repeat-safe: if order is already authorized, returns current order details.
    """
    if not order_id or not str(order_id).strip():
        raise ValueError("A valid order_id must be provided.")

    settings = get_settings()
    access_token = get_access_token()
    clean_id = str(order_id).strip()
    endpoint = f"{settings.base_url}/v2/checkout/orders/{clean_id}/authorize"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    try:
        response = requests.post(endpoint, headers=headers, json={}, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error while authorizing order: {exc}") from exc

    if response.status_code not in (200, 201):
        error_msg = response.text
        try:
            error_json = response.json()
            error_name = str(error_json.get("name", "")).upper()
            details = error_json.get("details", [])
            issues = [str(d.get("issue", "")).upper() for d in details if isinstance(d, dict)]

            # Repeat-safe check: return current details if already authorized
            if (
                error_name == "ORDER_ALREADY_AUTHORIZED"
                or "ORDER_ALREADY_AUTHORIZED" in issues
                or "already authorized" in error_msg.lower()
            ):
                return get_payment_details(clean_id)

            if details and isinstance(details, list) and "description" in details[0]:
                error_msg = f"{error_json.get('message', '')}: {details[0]['description']}"
            else:
                error_msg = error_json.get("message", response.text)
        except Exception:
            pass

        raise RuntimeError(
            f"Failed to authorize order '{clean_id}' [HTTP {response.status_code}]: {error_msg}"
        )

    data = response.json()

    authorization_id = None
    auth_status = None
    amount = None
    currency = None
    try:
        authorizations = data["purchase_units"][0]["payments"]["authorizations"]
        if authorizations:
            first_auth = authorizations[0]
            authorization_id = first_auth.get("id")
            auth_status = first_auth.get("status")
            amount = first_auth.get("amount", {}).get("value")
            currency = first_auth.get("amount", {}).get("currency_code")
    except (KeyError, IndexError, TypeError):
        pass

    return {
        "order_id": data.get("id"),
        "authorization_id": authorization_id,
        "authorization_status": auth_status,
        "status": data.get("status"),
        "payment_state": derive_payment_state(data),
        "amount": amount,
        "currency": currency,
    }


def capture_authorization(authorization_id: str) -> dict:
    """
    Capture an existing authorized payment hold using PayPal Payments API v2.
    """
    if not authorization_id or not str(authorization_id).strip():
        raise ValueError("A valid authorization_id must be provided.")

    settings = get_settings()
    access_token = get_access_token()
    clean_id = str(authorization_id).strip()
    endpoint = f"{settings.base_url}/v2/payments/authorizations/{clean_id}/capture"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    try:
        response = requests.post(endpoint, headers=headers, json={}, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error while capturing authorization: {exc}") from exc

    if response.status_code not in (200, 201):
        error_msg = response.text
        try:
            error_json = response.json()
            details = error_json.get("details", [])
            if details and isinstance(details, list) and "description" in details[0]:
                error_msg = f"{error_json.get('message', '')}: {details[0]['description']}"
            else:
                error_msg = error_json.get("message", response.text)
        except Exception:
            pass
        raise RuntimeError(
            f"Failed to capture authorization '{clean_id}' [HTTP {response.status_code}]: {error_msg}"
        )

    data = response.json()
    amount_info = data.get("amount") or {}
    amount_val = amount_info.get("value")
    curr_val = amount_info.get("currency_code")

    if not amount_val:
        gross = data.get("seller_receivable_breakdown", {}).get("gross_amount", {})
        if gross:
            amount_val = gross.get("value")
            curr_val = gross.get("currency_code")

    capture_id = data.get("id")

    return {
        "order_id": None,
        "authorization_id": clean_id,
        "capture_id": capture_id,
        "status": data.get("status"),
        "payment_state": "PAID" if str(data.get("status", "")).upper() == "COMPLETED" else derive_payment_state(data),
        "amount": amount_val,
        "currency": curr_val,
    }


def void_authorization(authorization_id: str) -> dict:
    """
    Void (cancel) an authorized payment hold using PayPal Payments API v2.
    """
    if not authorization_id or not str(authorization_id).strip():
        raise ValueError("A valid authorization_id must be provided.")

    settings = get_settings()
    access_token = get_access_token()
    clean_id = str(authorization_id).strip()
    endpoint = f"{settings.base_url}/v2/payments/authorizations/{clean_id}/void"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(endpoint, headers=headers, json={}, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error while voiding authorization: {exc}") from exc

    if response.status_code not in (200, 204):
        error_msg = response.text
        try:
            error_json = response.json()
            details = error_json.get("details", [])
            if details and isinstance(details, list) and "description" in details[0]:
                error_msg = f"{error_json.get('message', '')}: {details[0]['description']}"
            else:
                error_msg = error_json.get("message", response.text)
        except Exception:
            pass
        raise RuntimeError(
            f"Failed to void authorization '{clean_id}' [HTTP {response.status_code}]: {error_msg}"
        )

    return {
        "order_id": None,
        "authorization_id": clean_id,
        "status": "VOIDED",
        "payment_state": "VOIDED",
        "amount": None,
        "currency": None,
    }
