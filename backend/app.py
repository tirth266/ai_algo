"""
Compatibility ASGI entrypoint for production.

This module re-exports the FastAPI application instance from main.py, 
allowing it to be imported as 'app:app' from the backend folder 
or 'backend.app:app' from the project root.
"""

try:
    from backend.main import app
except (ImportError, ModuleNotFoundError):
    from main import app
