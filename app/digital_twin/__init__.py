"""
digital_twin/__init__.py

Usage in main.py:
─────────────────
    from app.digital_twin import router, start_twin_worker

    app.include_router(router)

    @app.on_event("startup")
    def on_startup():
        start_twin_worker()
"""

from .routes import router # Imports the FastAPI router object, which defines all HTTP endpoints for the Digital Twin.
from .twin_worker import start_twin_worker  #Imports the function to launch the background worker that keeps simulating vessel positions.

__all__ = ["router", "start_twin_worker"]
#__all__ = ["router", "start_twin_worker"]: This defines the public API of the digital_twin module. When you do from app.digital_twin import *, only these two names are exported