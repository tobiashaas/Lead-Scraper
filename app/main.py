"""
FastAPI Main Application
KR Lead Scraper REST API
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.database.database import check_db_connection
from app.utils.logger import setup_logging
from app.api import companies, scraping, health

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


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


# Create FastAPI app
app = FastAPI(
    title="KR Lead Scraper API",
    description="Automated B2B Lead Generation System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    debug=settings.debug
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://kunze-ritter.de"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.debug else "An error occurred"
        }
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(scraping.router, prefix="/api/v1/scraping", tags=["Scraping"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "KR Lead Scraper API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
