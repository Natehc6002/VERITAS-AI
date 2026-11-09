"""FastAPI application factory and middleware configuration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analysis, auth, compare, documents, extraction, health, investigations
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import VeritasError

logger = logging.getLogger(__name__)

API_VERSION = "1.2.0"

TAGS_METADATA = [
    {"name": "health", "description": "Service availability checks."},
    {
        "name": "auth",
        "description": "Account registration, login and current user context.",
    },
    {
        "name": "investigations",
        "description": "Owner-scoped investigation containers for documents.",
    },
    {
        "name": "documents",
        "description": "Secure document upload, listing, inspection and deletion.",
    },
    {
        "name": "extraction",
        "description": "Native PDF text extraction and OCR-backed text retrieval.",
    },
    {
        "name": "analysis",
        "description": (
            "Document classification, entity extraction, forensic indicators, "
            "evidence traceability and dashboard statistics."
        ),
    },
    {
        "name": "comparison",
        "description": "Explainable cross-document comparison and conflict detection.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("%s backend started (debug=%s)", settings.app_name, settings.debug)
    yield


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        description=(
            "AI-powered Document Forensics and Contextual Intelligence System. "
            "Provides secure document ingestion, metadata and text extraction, "
            "explainable classification/indicators and cross-document comparison."
        ),
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(application)

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(investigations.router)
    application.include_router(documents.router)
    application.include_router(extraction.router)
    application.include_router(analysis.router)
    application.include_router(compare.router)
    return application


def _register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(VeritasError)
    async def _handle_domain_error(request: Request, exc: VeritasError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @application.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected internal error occurred."},
        )


app = create_app()
