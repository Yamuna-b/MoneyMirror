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

import logging
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings
from routes import router as api_router
from deps import get_db

logger = logging.getLogger("money_mirror")
logging.basicConfig(level=logging.INFO)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(title="Money Mirror API", version="2.1.0")

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception during request {request.method} {request.url.path}: {str(exc)}",
            exc_info=True,
        )
        if not cfg.is_production:
            return JSONResponse(status_code=500, content={"detail": str(exc)})
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            f"Validation error during request {request.method} {request.url.path}: {exc.errors()}"
        )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    allow_credentials = "*" not in cfg.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(api_router, prefix="/api")

    @app.get("/")
    def serve_frontend():
        base = os.path.dirname(os.path.abspath(__file__))
        frontend_path = os.path.join(base, "money_mirror_app.html")
        if os.path.exists(frontend_path):
            return FileResponse(frontend_path)
        return {"message": "Money Mirror API. Place money_mirror_app.html next to main.py."}

    @app.get("/health")
    def health(db=Depends(get_db)):
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
            
        return {
            "status": "ok" if "error" not in db_status else "degraded",
            "service": "Money Mirror API",
            "version": "2.1.0",
            "environment": cfg.environment,
            "database": db_status,
        }

    return app


app = create_app()
