"""
Money Mirror — ASGI application factory.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from routes import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Money Mirror API", version="2.0.0")

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        import traceback

        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/")
    def serve_frontend():
        base = os.path.dirname(os.path.abspath(__file__))
        frontend_path = os.path.join(base, "money_mirror_app.html")
        if os.path.exists(frontend_path):
            return FileResponse(frontend_path)
        return {"message": "Money Mirror API. Place money_mirror_app.html next to main.py."}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "Money Mirror API", "version": "2.0.0"}

    return app


app = create_app()
