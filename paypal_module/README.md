# ProofBridge AI - PayPal Sandbox Module

This module provides the PayPal Sandbox integration for the ProofBridge AI dispute platform. It supports direct payments (immediate capture) and authorization holds (two-step lock and release or capture) using standard REST calls without runtime SDK dependencies.

> **Complete Documentation**: For full API contracts, endpoint definitions, security guidelines, and step-by-step frontend/backend integration instructions, refer to [**`PAYPAL_MODULE.md`**](./PAYPAL_MODULE.md).

---

## Files in this Module

* [`PAYPAL_MODULE.md`](./PAYPAL_MODULE.md): Complete module documentation and integration guide.
* [`config.py`](./config.py): Lazy environment configuration loader and validator.
* [`paypal_client.py`](./paypal_client.py): REST OAuth2 client providing temporary Bearer tokens.
* [`payments.py`](./payments.py): Core payment functions (create, capture, authorize, capture-authorization, void, details).
* [`router.py`](./router.py): FastAPI APIRouter ready for inclusion in the ProofBridge backend.
* [`dev_server.py`](./dev_server.py): Lightweight local FastAPI server for manual testing at `/docs`.
* [`check_connection.py`](./check_connection.py): CLI diagnostic script to check `.env` configuration.
* [`test_create_order.py`](./test_create_order.py): CLI script to test order creation.
* [`test_capture.py`](./test_capture.py): CLI script to test order capture.
* [`test_hold_flow.py`](./test_hold_flow.py): CLI script to test the full authorization hold lifecycle.
* [`.env.example`](./.env.example): Template for required sandbox environment variables.
* [`requirements.txt`](./requirements.txt): Runtime dependencies (`requests`, `python-dotenv`, `fastapi`, `uvicorn`).
* [`__init__.py`](./__init__.py): Package initializer enabling relative and absolute imports.

---

## Quick Start (Windows PowerShell)

```powershell
# 1. Navigate to the module directory
cd paypal_module

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env from template and add your sandbox credentials
Copy-Item .env.example .env

# 5. Verify configuration and sandbox connectivity
python check_connection.py

# 6. Run the local dev server and test via Swagger UI
python dev_server.py
# Open: http://127.0.0.1:8000/docs
```
