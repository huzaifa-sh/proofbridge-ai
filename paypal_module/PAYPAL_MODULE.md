# PayPal Module Integration Guide

---

## 0. SUMMARY FOR HUMANS
This module handles PayPal Sandbox payments for ProofBridge AI dispute cases without exposing credentials. It supports two flows: direct payments (immediate capture) and authorization holds (locking funds for later capture or release). It provides callable Python functions and a plug-and-play FastAPI router with clean JSON error handling. Credentials are never logged, committed to git, or returned in API responses. Person 2 (backend) integrates the router or functions into FastAPI; Person 1 (frontend) redirects buyers to PayPal's approval URL. All operations run safely inside PayPal's sandbox environment.

---

## 1. FOR AI AGENTS (RULES)
1. **Server-Side Only**: This module executes strictly on the backend. Never invoke PayPal APIs from client-side code.
2. **Never Call PayPal From Frontend**: The frontend only redirects the buyer to `approval_link` and reads `?token=ORDER_ID` on return.
3. **No Secrets in Chat**: Never ask the user to share Client ID, Client Secret, or tokens in conversation.
4. **No Secrets in Code/Logs**: Never hardcode, print, or log credentials, full access tokens, or sensitive headers.
5. **Prompt Before Installing**: Ask user permission before installing new packages or system tools.
6. **Sandbox Isolation**: Use `https://api-m.sandbox.paypal.com` only; never point to live PayPal in this environment.

---

## 2. HOW THE SANDBOX WORKS
* **Sandbox = Simulated PayPal**: Real money never moves; test accounts simulate buyers and merchants.
* **Buyer vs. Seller**: A Sandbox **Personal** account acts as the client/buyer; a Sandbox **Business** account acts as the merchant/seller.
* **Single Merchant App**: The `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` identify the backend application and route all demo funds to one sandbox merchant account.
* **Production Difference**: In production, routing funds to multiple freelance sellers requires PayPal Marketplace or Multiparty Platform onboarding.

---

## 3. THE TWO PAYMENT MODES & DECISION GUIDE

### Direct Mode (`capture`)
* **Core Concept**: Money moves when the buyer approves.
* **Lifecycle**:
  1. Backend calls `create_payment(..., mode="capture")` (intent `CAPTURE`).
  2. Buyer approves payment via PayPal `approval_link`.
  3. Backend calls `capture_payment(order_id)` immediately upon buyer return.
* **Endpoints**: `POST /create` -> `POST /{order_id}/capture`.
* **When to use in ProofBridge**: Instant dispute filing fees, document purchases, or non-refundable platform service charges.

### Hold Mode (`authorize`)
* **Core Concept**: Money is reserved and only moves when the backend captures after approval.
* **Lifecycle**:
  1. Backend calls `create_payment(..., mode="authorize")` (intent `AUTHORIZE`).
  2. Buyer approves the hold via `approval_link`.
  3. Backend calls `authorize_payment(order_id)` to lock the hold and receive an `authorization_id`.
  4. **Resolution Outcome**:
     * Seller awarded funds: Backend calls `capture_authorization(authorization_id)`.
     * Client keeps money / case canceled: Backend calls `void_authorization(authorization_id)`.
* **Endpoints**: `POST /create` -> `POST /{order_id}/authorize` -> `POST /authorizations/{id}/capture` or `.../void`.
* **Important Note**: This is a standard authorization hold, **not a legal escrow service**. PayPal documents an authorization validity window (reported as about 29 days, with a shorter honor period). Confirm exact numbers in PayPal's docs.
* **When to use in ProofBridge**: Escrow-style case dispute deposits where funds must be held while evidence is reviewed, then released to the winner or refunded upon case resolution.

---

## 4. FILE MAP
* **[`config.py`](./config.py)**: Loads and lazily validates environment variables from `.env` via `get_settings()` and `get_missing_settings()`.
* **[`paypal_client.py`](./paypal_client.py)**: Authenticates with PayPal OAuth 2.0 (`/v1/oauth2/token`) using direct REST requests and returns temporary Bearer tokens.
* **[`payments.py`](./payments.py)**: Core payment logic implementing order creation, capture, authorization, capture-authorization, void operations, and state derivation.
* **[`router.py`](./router.py)**: FastAPI router exposing standardized REST endpoints with Pydantic validation, safe error mapping (502 for upstream failures), and repeat-safe operations.
* **[`dev_server.py`](./dev_server.py)**: Minimal local FastAPI server mounting `router.py` at `/paypal` with auto-redirect to `/docs`.
* **[`check_connection.py`](./check_connection.py)**: CLI diagnostic tool to verify PayPal sandbox credentials and report missing variables without printing secrets.
* **[`test_create_order.py`](./test_create_order.py)**: CLI script to test creating a live direct capture order.
* **[`test_capture.py`](./test_capture.py)**: CLI script to capture an approved order and display payer information.
* **[`test_hold_flow.py`](./test_hold_flow.py)**: CLI script providing a step-by-step test for the complete hold-and-capture or void lifecycle.
* **[`requirements.txt`](./requirements.txt)**: Lists required Python libraries (`requests`, `python-dotenv`, `fastapi`, `uvicorn`).
* **[`.env.example`](./.env.example)**: Safe template demonstrating required and optional environment variable names.
* **[`__init__.py`](./__init__.py)**: Package initializer exposing public payment and router functions with dual-import support.

---

## 5. SETUP
* **Python Floor**: Python 3.10+ (tested on Python 3.13).
* **Virtual Environment (Windows PowerShell)**:
  ```powershell
  cd paypal_module
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```
* **Dependencies in `requirements.txt`**:
  * `requests`: Issues HTTPS REST requests to PayPal endpoints.
  * `python-dotenv`: Safely parses variables from `.env` into `os.environ`.
  * `fastapi`: API framework powering request validation and routers.
  * `uvicorn`: ASGI web server executing the local dev server.
* **Configure Environment**:
  ```powershell
  Copy-Item .env.example .env
  ```
  Set these variables inside `.env`:
  * `PAYPAL_CLIENT_ID` (Required): Sandbox app Client ID.
  * `PAYPAL_CLIENT_SECRET` (Required): Sandbox app Secret.
  * `PAYPAL_BASE_URL` (Required): `https://api-m.sandbox.paypal.com`.
  * `FRONTEND_RETURN_URL` (Optional): Redirect URL after buyer approves.
  * `FRONTEND_CANCEL_URL` (Optional): Redirect URL if buyer cancels.
* **Run Dev Server & Open Docs**:
  ```powershell
  python dev_server.py
  ```
  Open interactive Swagger UI: **http://127.0.0.1:8000/docs**
* **APIMatic Requirement**: **NOT required at runtime**. The runtime uses direct HTTP requests with standard Python libraries. APIMatic is strictly design-time reference material.

---

## 6. APIMATIC (REFERENCE ONLY)
* **What it is**: APIMatic provides local reference schemas and specifications that helped guide development of the REST payload contracts for the PayPal Orders API v2.
* **Runtime Status**: **NOT needed to run this module.** It is not a runtime dependency and no daemon or MCP server is executed.
* **Reference Command**: Can optionally be explored via `npx context-plugins install paypal` (Node 18+) to inspect PayPal API definitions, but this is completely optional.

---

## 7. ENDPOINTS & API CONTRACTS

> **Note on Router Prefix**: The URL prefix is entirely the backend's choice (e.g. `/paypal` or `/api/paypal`). In the examples below, `/paypal` is used matching `dev_server.py`.

### Normalized `payment_state` Values
The module computes a unified `payment_state` based on PayPal's internal order and payment objects:

| `payment_state` | Description |
| :--- | :--- |
| `PENDING_APPROVAL` | Order created (`intent` CAPTURE or AUTHORIZE); buyer has not yet approved it on PayPal. |
| `APPROVED` | Buyer has approved the order at the PayPal checkout page; ready for capture or authorization. |
| `HELD` | Funds are successfully authorized and locked on hold (`intent=AUTHORIZE`, authorization `CREATED`). |
| `PAID` | Funds have been successfully captured and moved into the merchant account. |
| `VOIDED` | Authorization hold was canceled and released; funds returned to the buyer. |
| `EXPIRED` | Authorization hold expired before being captured. |
| `FAILED` | Order or payment creation, capture, or authorization was denied or failed. |

### Standard Payment Details JSON
Detail responses return these normalized fields (`null` when not applicable):
```json
{
  "order_id": "5O190127TN364715T",
  "status": "COMPLETED",
  "payment_state": "PAID",
  "intent": "CAPTURE",
  "amount": "100.00",
  "currency": "USD",
  "payer_email": "buyer@example.com",
  "case_id": "CASE-001",
  "authorization_id": null,
  "authorization_status": null,
  "capture_id": "7AB12345CD67890"
}
```

### 1. `POST /create`
* **Request JSON**:
  ```json
  {"case_id": "CASE-001", "amount": "100.00", "currency": "USD", "mode": "capture"}
  ```
  *(Validation: `amount` must be positive with at most 2 decimal places; `currency` must be 3 letters; `mode` must be "capture" or "authorize"; `case_id` must be non-empty and <= 100 characters).*
* **Success JSON (201 Created)**:
  ```json
  {"order_id": "5O190127TN364715T", "status": "CREATED", "approval_link": "https://www.sandbox.paypal.com/checkoutnow?token=5O190127TN364715T"}
  ```
* **Error JSON (422 Unprocessable Entity)**:
  ```json
  {"detail": "Amount must be a positive decimal with at most 2 decimal places (e.g. '10.50')."}
  ```
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8000/paypal/create -H "Content-Type: application/json" -d '{"case_id":"CASE-001","amount":"100.00","currency":"USD","mode":"capture"}'
  ```

### 2. `POST /{order_id}/capture`
* **Success JSON (200 OK)**:
  ```json
  {"order_id": "5O190127TN364715T", "status": "COMPLETED", "payment_state": "PAID", "intent": "CAPTURE", "amount": "100.00", "currency": "USD", "payer_email": "buyer@example.com", "case_id": "CASE-001", "authorization_id": null, "authorization_status": null, "capture_id": "7AB12345CD67890"}
  ```
  *(Repeat-safe: If already captured, returns 200 OK with the latest payment state).*
* **Error JSON (422 Unprocessable Entity)**:
  ```json
  {"detail": "UNPROCESSABLE_ENTITY: ORDER_NOT_APPROVED"}
  ```
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8000/paypal/5O190127TN364715T/capture
  ```

### 3. `POST /{order_id}/authorize`
* **Success JSON (200 OK)**:
  ```json
  {"order_id": "5O190127TN364715T", "authorization_id": "87349102US839201A", "status": "COMPLETED", "payment_state": "HELD", "amount": "100.00", "currency": "USD"}
  ```
  *(Repeat-safe: If already authorized, returns 200 OK with the current hold details).*
* **Error JSON (422 Unprocessable Entity)**:
  ```json
  {"detail": "UNPROCESSABLE_ENTITY: ORDER_NOT_APPROVED"}
  ```
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8000/paypal/5O190127TN364715T/authorize
  ```

### 4. `POST /authorizations/{authorization_id}/capture`
* **Success JSON (200 OK)**:
  ```json
  {"order_id": null, "authorization_id": "87349102US839201A", "status": "COMPLETED", "payment_state": "PAID", "amount": "100.00", "currency": "USD"}
  ```
* **Error JSON (422 Unprocessable Entity)**:
  ```json
  {"detail": "AUTHORIZATION_ALREADY_CAPTURED: The authorization has already been captured."}
  ```
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8000/paypal/authorizations/87349102US839201A/capture
  ```

### 5. `POST /authorizations/{authorization_id}/void`
* **Success JSON (200 OK)**:
  ```json
  {"order_id": null, "authorization_id": "87349102US839201A", "status": "VOIDED", "payment_state": "VOIDED", "amount": null, "currency": null}
  ```
* **Error JSON (422 Unprocessable Entity)**:
  ```json
  {"detail": "AUTHORIZATION_ALREADY_VOIDED: The authorization has already been voided."}
  ```
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8000/paypal/authorizations/87349102US839201A/void
  ```

### 6. `GET /{order_id}`
* **Success JSON (200 OK)**:
  ```json
  {"order_id": "5O190127TN364715T", "status": "CREATED", "payment_state": "PENDING_APPROVAL", "intent": "CAPTURE", "amount": "100.00", "currency": "USD", "payer_email": null, "case_id": "CASE-001", "authorization_id": null, "authorization_status": null, "capture_id": null}
  ```
* **Error JSON (404 Not Found)**:
  ```json
  {"detail": "RESOURCE_NOT_FOUND: The specified resource does not exist."}
  ```
* **cURL**:
  ```bash
  curl -X GET http://127.0.0.1:8000/paypal/5O190127TN364715T
  ```

---

## 8. HOW TO INTEGRATE (PERSON 2: BACKEND LEAD)

### Security: Who May Call What
Moving money is a sensitive operation. In a production deployment:
* **Endpoints that move or lock money** (`/{order_id}/capture`, `/{order_id}/authorize`, `/authorizations/{id}/capture`, and `/authorizations/{id}/void`) **must never be left unauthenticated or exposed directly to client whims**. They should be restricted to verified users and backend administrators or automated background workers.
* **Endpoints that initiate or check state** (`/create` and `/{order_id}`) can be called by authenticated frontend users for their own cases.
* **FastAPI Dependency Injection**: Person 2 should secure the router using dependencies:
  ```python
  from fastapi import Depends, HTTPException
  from paypal_module.router import router as paypal_router

  # Example authentication dependency
  async def verify_auth_token(token: str = Depends(...)):
      if not token:
          raise HTTPException(status_code=401, detail="Unauthorized")

  # Mount with authentication dependency:
  app.include_router(
      paypal_router,
      prefix="/api/paypal",  # Prefix choice is flexible
      dependencies=[Depends(verify_auth_token)]
  )
  ```

### Option A: Mount `router.py` (Fastest for REST API)
Best when Person 2 wants standard endpoints exposed directly:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from paypal_module.router import router as paypal_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(paypal_router, prefix="/api/paypal")
```

### Option B: Import Python Functions (Custom Logic / DB Transactions)
Best when the backend needs to manage PostgreSQL state machine transitions in the same transaction:
```python
from paypal_module.payments import (
    create_payment,
    capture_payment,
    authorize_payment,
    capture_authorization,
    void_authorization,
    get_payment_details
)

# Example: create order and store in database
order = create_payment(amount="150.00", currency="USD", case_id="CASE-99", mode="authorize")
# DB.save(case_id="CASE-99", order_id=order["order_id"], status=order["status"])
```

### Database Storage Per Case
Store these fields in your PostgreSQL `cases` or `payments` table:
* `paypal_order_id` (string, nullable)
* `paypal_authorization_id` (string, nullable)
* `paypal_capture_id` (string, nullable)
* `payment_state` (string: `PENDING_APPROVAL`, `APPROVED`, `HELD`, `PAID`, `VOIDED`, `EXPIRED`, `FAILED`)
* `amount` (string or decimal)
* `currency` (string, 3 uppercase characters)
* `payer_email` (string, nullable)

---

## 9. FRONTEND FLOW (PERSON 1: NEXT.JS LEAD)
1. **Initiate**: Next.js calls backend `POST /api/paypal/create`.
2. **Redirect**: Backend returns `approval_link`. Frontend redirects buyer:
   ```javascript
   window.location.href = data.approval_link;
   ```
3. **Approval**: Buyer logs into PayPal sandbox and clicks "Agree and Continue".
4. **Return Redirect**: PayPal redirects back to `FRONTEND_RETURN_URL` with query parameters:
   ```
   https://yourfrontend.com/payment/success?token=5O190127TN364715T&PayerID=XYZ123
   ```
   *(PayPal passes the order ID inside the `token` query parameter).*
5. **Finalize**: The frontend return page reads `token` from URL parameters:
   ```javascript
   const orderId = new URLSearchParams(window.location.search).get("token");
   // Call backend to capture or authorize:
   await fetch(`/api/paypal/${orderId}/capture`, { method: "POST" });
   ```
6. **Cancellation**: If the buyer clicks cancel, PayPal redirects to `FRONTEND_CANCEL_URL?token=...`.

---

## 10. TROUBLESHOOTING
* **`ModuleNotFoundError: No module named 'dotenv'`**: Virtual environment is not activated. Run `.\venv\Scripts\Activate.ps1`.
* **`401 invalid_client` / `502 Upstream Authentication Failed`**: Client ID or Secret in `.env` is invalid or belongs to Live instead of Sandbox.
* **`ValueError: Missing required PayPal configuration in .env`**: Required variables are missing. Run `python check_connection.py` to identify which specific variables are absent.
* **Return URL Errors**: `FRONTEND_RETURN_URL` must be a valid absolute URL if defined, or omitted.
* **`422 UNPROCESSABLE_ENTITY: ORDER_NOT_APPROVED`**: Calling capture or authorize before the buyer finished approving in PayPal.
* **Expired or Already-Captured Hold**: Attempting to capture an expired or already finalized authorization returns a 422 error describing the authorization's final state.

---

## 11. KNOWN LIMITATIONS & VERIFICATION STATUS
* **Sandbox Only**: Configured strictly for `api-m.sandbox.paypal.com`.
* **Single Merchant Account**: All payments credit the single Sandbox Business account configured in `.env`.
* **Verification Status Table**:

| Operation | Implementation | Tested by owner (date) |
| :--- | :--- | :--- |
| `check_connection.py` | Token OAuth2 | Tested by owner (2026-11-09) |
| `create_payment` (capture mode) | Orders v2 POST | Tested by owner (2026-11-09) |
| `capture_payment` | Orders v2 POST capture | Tested by owner (2026-11-09) |
| `get_payment_details` | Orders v2 GET order | Tested by owner (2026-11-09) |
| `create_payment` (authorize mode) | Orders v2 POST auth | Tested by owner (2026-11-09) |
| `authorize_payment` | Orders v2 POST authorize | Tested by owner (2026-11-09) |
| `capture_authorization` | Payments v2 POST capture | Tested by owner (2026-11-09) |
| `void_authorization` | Payments v2 POST void | Tested by owner (2026-11-09) |
| `router.py` Endpoints | FastAPI APIRouter | Tested by owner (2026-11-09) |
