"""
FastAPI Router for ProofBridge AI PayPal Integration.

Exposes PayPal Sandbox order and authorization operations:
1. POST /create: Creates a new order and returns an approval link.
2. POST /{order_id}/capture: Captures an approved order (mode='capture').
3. POST /{order_id}/authorize: Authorizes an approved order (mode='authorize').
4. POST /authorizations/{authorization_id}/capture: Captures an existing authorization hold.
5. POST /authorizations/{authorization_id}/void: Voids an authorization hold.
6. GET /{order_id}: Fetches current payment details for an order.
"""

import re
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

try:
    from .payments import (
        create_payment,
        capture_payment,
        get_payment_details,
        authorize_payment,
        capture_authorization,
        void_authorization,
    )
except ImportError:
    from payments import (
        create_payment,
        capture_payment,
        get_payment_details,
        authorize_payment,
        capture_authorization,
        void_authorization,
    )

router = APIRouter(tags=["PayPal"])


# ==============================================================================
# Pydantic Schemas & Validation
# ==============================================================================

class CreatePaymentRequest(BaseModel):
    case_id: str = Field(
        ...,
        description="ProofBridge AI internal dispute case identifier (1-100 characters)"
    )
    amount: str = Field(
        ...,
        description="Payment amount as positive decimal with at most 2 decimal places (e.g. '100.00')"
    )
    currency: str = Field(
        default="USD",
        description="Three-letter ISO currency code (e.g. 'USD')"
    )
    mode: str = Field(
        default="capture",
        description="Payment mode: 'capture' (default) or 'authorize'"
    )

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        cleaned = v.strip() if isinstance(v, str) else ""
        if not cleaned or len(cleaned) > 100:
            raise ValueError("case_id must be non-empty and at most 100 characters.")
        return cleaned

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        cleaned = v.strip() if isinstance(v, str) else ""
        if not re.match(r"^\d+(\.\d{1,2})?$", cleaned):
            raise ValueError(
                "amount must be a positive decimal with at most 2 decimal places (e.g. '10.00' or '150')."
            )
        if float(cleaned) <= 0:
            raise ValueError("amount must be greater than zero.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        cleaned = v.strip().upper() if isinstance(v, str) else ""
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("currency must be a valid 3-letter currency code (e.g. 'USD', 'EUR').")
        return cleaned

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        cleaned = v.strip().lower() if isinstance(v, str) else ""
        if cleaned not in ("capture", "authorize"):
            raise ValueError("mode must be either 'capture' or 'authorize'.")
        return cleaned


class CreatePaymentResponse(BaseModel):
    order_id: str = Field(..., description="PayPal's unique order identifier")
    status: str = Field(..., description="Current order state (e.g. 'CREATED')")
    approval_link: Optional[str] = Field(
        default=None,
        description="Checkout URL where the buyer approves payment"
    )


class PaymentDetailsResponse(BaseModel):
    order_id: Optional[str] = Field(default=None, description="PayPal order identifier")
    status: Optional[str] = Field(default=None, description="Order status ('CREATED', 'COMPLETED', etc.)")
    payment_state: Optional[str] = Field(
        default=None,
        description="Normalized payment state ('PENDING_APPROVAL', 'APPROVED', 'HELD', 'PAID', 'VOIDED', 'EXPIRED', 'FAILED')"
    )
    intent: Optional[str] = Field(default=None, description="Payment intent ('CAPTURE' or 'AUTHORIZE')")
    amount: Optional[str] = Field(default=None, description="Payment amount string")
    currency: Optional[str] = Field(default=None, description="Three-letter currency code")
    payer_email: Optional[str] = Field(default=None, description="PayPal account email of the buyer")
    case_id: Optional[str] = Field(default=None, description="ProofBridge AI dispute case identifier")
    authorization_id: Optional[str] = Field(default=None, description="Authorization ID if intent was AUTHORIZE")
    authorization_status: Optional[str] = Field(default=None, description="Status of the authorization hold")
    capture_id: Optional[str] = Field(default=None, description="Capture transaction ID if funds captured")


class AuthorizationResponse(BaseModel):
    order_id: Optional[str] = Field(default=None, description="PayPal order identifier")
    authorization_id: Optional[str] = Field(default=None, description="PayPal authorization identifier")
    authorization_status: Optional[str] = Field(default=None, description="Status of authorization hold")
    status: Optional[str] = Field(default=None, description="Status ('CREATED', 'COMPLETED', 'VOIDED', etc.)")
    payment_state: Optional[str] = Field(default=None, description="Normalized state ('HELD', 'PAID', 'VOIDED', etc.)")
    amount: Optional[str] = Field(default=None, description="Amount string")
    currency: Optional[str] = Field(default=None, description="Currency code")


# ==============================================================================
# Error Mapping
# ==============================================================================

def _handle_paypal_exception(exc: Exception) -> HTTPException:
    """
    Convert an internal exception to a safe FastAPI HTTPException.
    - Keeps 400, 404, 422 from PayPal as they are.
    - Maps 401, 403, 5xx and network failures to 502 Bad Gateway.
    - Never includes tokens, headers, or secrets.
    """
    error_str = str(exc)

    match = re.search(r"\[HTTP\s+(\d{3})\]", error_str)
    raw_status = int(match.group(1)) if match else None

    # Clean message to present to client without internal system paths or secrets
    clean_message = error_str
    if ":" in clean_message:
        clean_message = clean_message.split(":", 1)[-1].strip()

    # Pass through client validation and resource errors; map infrastructure/auth/server errors to 502
    if raw_status in (400, 404, 422):
        final_status = raw_status
    else:
        final_status = status.HTTP_502_BAD_GATEWAY

    return HTTPException(status_code=final_status, detail=clean_message)


# ==============================================================================
# Endpoints
# ==============================================================================

@router.post(
    "/create",
    response_model=CreatePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new PayPal payment order"
)
def create_order(request: CreatePaymentRequest):
    """
    Create a PayPal order for a ProofBridge AI case.

    Returns the PayPal `order_id`, initial `status`, and the `approval_link`.
    """
    try:
        result = create_payment(
            amount=request.amount,
            currency=request.currency,
            case_id=request.case_id,
            mode=request.mode
        )
        return CreatePaymentResponse(
            order_id=result.get("order_id"),
            status=result.get("status"),
            approval_link=result.get("approval_link")
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise _handle_paypal_exception(exc)


@router.post(
    "/{order_id}/capture",
    response_model=PaymentDetailsResponse,
    status_code=status.HTTP_200_OK,
    summary="Capture an approved PayPal payment order"
)
def capture_order(order_id: str):
    """
    Capture the funds for an approved order.
    Repeat-safe: returns current order details if already captured.
    """
    try:
        capture_result = capture_payment(order_id)
        try:
            details = get_payment_details(order_id)
        except Exception:
            details = {}

        return PaymentDetailsResponse(
            order_id=order_id,
            status=details.get("status") or capture_result.get("status"),
            payment_state=capture_result.get("payment_state") or details.get("payment_state"),
            intent=details.get("intent") or "CAPTURE",
            amount=capture_result.get("amount") or details.get("amount"),
            currency=capture_result.get("currency") or details.get("currency"),
            payer_email=details.get("payer_email"),
            case_id=details.get("case_id"),
            capture_id=capture_result.get("capture_id") or details.get("capture_id")
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise _handle_paypal_exception(exc)


@router.post(
    "/{order_id}/authorize",
    response_model=AuthorizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Authorize an approved PayPal order"
)
def authorize_order(order_id: str):
    """
    Authorize funds for an approved order whose mode was 'authorize'.
    Repeat-safe: returns current order details if already authorized.
    """
    try:
        result = authorize_payment(order_id)
        return AuthorizationResponse(
            order_id=result.get("order_id"),
            authorization_id=result.get("authorization_id"),
            authorization_status=result.get("authorization_status"),
            status=result.get("status"),
            payment_state=result.get("payment_state"),
            amount=result.get("amount"),
            currency=result.get("currency")
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise _handle_paypal_exception(exc)


@router.post(
    "/authorizations/{authorization_id}/capture",
    response_model=AuthorizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Capture an authorized payment hold"
)
def capture_auth(authorization_id: str):
    """
    Capture funds from an existing authorization hold.
    """
    try:
        result = capture_authorization(authorization_id)
        return AuthorizationResponse(
            order_id=result.get("order_id"),
            authorization_id=result.get("authorization_id"),
            status=result.get("status"),
            payment_state=result.get("payment_state"),
            amount=result.get("amount"),
            currency=result.get("currency")
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise _handle_paypal_exception(exc)


@router.post(
    "/authorizations/{authorization_id}/void",
    response_model=AuthorizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Void (cancel) an authorized payment hold"
)
def void_auth(authorization_id: str):
    """
    Void an authorization hold, releasing funds back to the buyer.
    """
    try:
        result = void_authorization(authorization_id)
        return AuthorizationResponse(
            order_id=result.get("order_id"),
            authorization_id=result.get("authorization_id"),
            status=result.get("status"),
            payment_state=result.get("payment_state"),
            amount=result.get("amount"),
            currency=result.get("currency")
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise _handle_paypal_exception(exc)


@router.get(
    "/{order_id}",
    response_model=PaymentDetailsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current PayPal payment details"
)
def get_order(order_id: str):
    """
    Retrieve real-time payment details and normalized status for an existing order.
    """
    try:
        details = get_payment_details(order_id)
        return PaymentDetailsResponse(
            order_id=details.get("order_id"),
            status=details.get("status"),
            payment_state=details.get("payment_state"),
            intent=details.get("intent"),
            amount=details.get("amount"),
            currency=details.get("currency"),
            payer_email=details.get("payer_email"),
            case_id=details.get("case_id"),
            authorization_id=details.get("authorization_id"),
            authorization_status=details.get("authorization_status"),
            capture_id=details.get("capture_id")
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise _handle_paypal_exception(exc)
