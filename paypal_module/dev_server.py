"""
Local Development Server for ProofBridge AI PayPal Module.

Used ONLY for testing the PayPal endpoints locally before Person 2
integrates `router.py` into the main FastAPI application.

Usage:
    uvicorn dev_server:app --reload --port 8000
    or:
    python dev_server.py
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

try:
    from .router import router as paypal_router
except ImportError:
    from router import router as paypal_router

# Initialize lightweight test app
app = FastAPI(
    title="ProofBridge AI - PayPal Module Dev Server",
    description="Local sandbox testing server for PayPal payment endpoints.",
    version="1.0.0"
)

# Include the PayPal router with the required prefix
app.include_router(paypal_router, prefix="/paypal")


@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    print("Starting local dev server at http://127.0.0.1:8000 ...")
    print("Open http://127.0.0.1:8000/docs to test endpoints interactively.")
    uvicorn.run("dev_server:app", host="127.0.0.1", port=8000, reload=True)
