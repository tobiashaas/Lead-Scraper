"""
FastAPI Main Application
KR Lead Scraper REST API
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api import bulk, companies, duplicates, export, health, scoring, scraping, webhooks
from app.core.config import settings
from app.core.sentry import init_sentry
from app.database.database import check_db_connection
from app.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Sentry
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager
    Runs on startup and shutdown
    """
    # Startup
    logger.info("🚀 Starting KR Lead Scraper API...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug Mode: {settings.debug}")

    if settings.prometheus_enabled and settings.prometheus_multiproc_dir:
        multiproc_dir = Path(settings.prometheus_multiproc_dir)
        try:
            multiproc_dir.mkdir(parents=True, exist_ok=True)
            removed_files = 0
            for item in multiproc_dir.iterdir():
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    removed_files += 1
            logger.info(
                "Cleaned Prometheus multiprocess directory",
                extra={
                    "path": str(multiproc_dir),
                    "removed_files": removed_files,
                },
            )
        except Exception as cleanup_error:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to prepare Prometheus multiprocess directory",
                extra={"path": str(multiproc_dir)},
                exc_info=cleanup_error,
            )

    # Check database connection
    db_ok = await check_db_connection()
    if not db_ok:
        logger.error("❌ Database connection failed!")
    else:
        logger.info("✅ Database connection OK")

    logger.info("✅ API started successfully")

    yield

    # Shutdown
    logger.info("🛑 Shutting down API...")


# Define security scheme for OpenAPI
def custom_openapi():
    """Custom OpenAPI schema with security schemes"""
    from fastapi.openapi.utils import get_openapi

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token obtained from /api/v1/auth/login endpoint. Format: Bearer {access_token}",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Create FastAPI app
app = FastAPI(
    title="KR Lead Scraper API",
    description="""## 🚀 Automated B2B Lead Generation System

### Features
- 🔍 **Multi-Source Scraping**: Extract leads from 11880, Gelbe Seiten, and more
- 🤖 **AI-Powered Enrichment**: Intelligent data extraction with Ollama integration
- 📊 **Lead Scoring**: Automated quality assessment and prioritization
- 🔄 **Duplicate Detection**: Smart deduplication with configurable thresholds
- ✅ **Contact Verification**: Email SMTP and phone validation
- 📤 **Export**: CSV, JSON exports with filtering
- 🔔 **Webhooks**: Real-time event notifications
- 🔐 **JWT Authentication**: Secure role-based access control

### Documentation
- [API Usage Guide](https://github.com/your-org/lead-scraper/blob/main/docs/API.md)
- [Production Deployment](https://github.com/your-org/lead-scraper/blob/main/docs/PRODUCTION.md)
- [API Versioning](https://github.com/your-org/lead-scraper/blob/main/docs/API-VERSIONING.md)

### Support
- GitHub: [Issues & Feature Requests](https://github.com/your-org/lead-scraper/issues)
- Email: support@kunze-ritter.de
    """,
    version=settings.api_version,
    terms_of_service="https://kunze-ritter.de/terms",
    contact={
        "name": "Kunze & Ritter GmbH",
        "url": "https://kunze-ritter.de",
        "email": "support@kunze-ritter.de",
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "Authentication", "description": "User registration, login, and token management"},
        {"name": "Companies", "description": "CRUD operations for company/lead management"},
        {"name": "Scraping", "description": "Scraping job creation and monitoring"},
        {"name": "Export", "description": "Data export in various formats (CSV, JSON)"},
        {"name": "Lead Scoring", "description": "Automated lead quality assessment"},
        {"name": "Bulk Operations", "description": "Mass operations on multiple companies"},
        {"name": "Webhooks", "description": "Event notification webhooks"},
        {"name": "Duplicates", "description": "Duplicate detection and management"},
        {"name": "Health", "description": "Health checks and metrics"},
    ],
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://staging.your-domain.com", "description": "Staging server"},
        {"url": "https://api.your-domain.com", "description": "Production server"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    debug=settings.debug,
)

# Logging & Metrics Middleware
from app.middleware import (
    LoggingMiddleware,
    MetricsMiddleware,
    RequestIDMiddleware,
    SentryContextMiddleware,
)

app.add_middleware(SentryContextMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Set custom OpenAPI schema
app.openapi = custom_openapi

# CORS Middleware
# Production-ready CORS configuration
# Configure allowed origins via CORS_ORIGINS environment variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Requested-With",
    ],
    expose_headers=["Content-Length", "Content-Type", "Content-Disposition"],
    max_age=settings.cors_max_age,
)


# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    from app.core.sentry import capture_exception, set_context
    from app.utils.structured_logger import get_structured_logger

    error_logger = get_structured_logger(__name__)

    # Log to structured logger
    error_logger.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
    )

    # Capture in Sentry with context
    set_context(
        "request",
        {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": str(request.query_params),
            "client_host": request.client.host if request.client else None,
        },
    )
    capture_exception(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.debug else "An error occurred",
        },
    )


# Include routers
from app.api import auth

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(scraping.router, prefix="/api/v1/scraping", tags=["Scraping"])
app.include_router(export.router, prefix="/api/v1", tags=["Export"])
app.include_router(scoring.router, prefix="/api/v1", tags=["Lead Scoring"])
app.include_router(bulk.router, prefix="/api/v1", tags=["Bulk Operations"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(duplicates.router, prefix="/api/v1", tags=["Duplicates"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "KR Lead Scraper API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
