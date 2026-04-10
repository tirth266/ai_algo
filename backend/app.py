"""
Compatibility ASGI entrypoint for production.

Different deploy targets may import this module either as `app:app`
from the backend directory or as `backend.app:app` from the repo root.
Re-export the same FastAPI application in both cases.
"""

try:
    from backend.main import app
except ModuleNotFoundError:
    from main import app
