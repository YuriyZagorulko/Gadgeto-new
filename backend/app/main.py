"""
Main FastAPI application entry point.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core import config, database
from app.api.v1 import router as api_router
from app.api.admin import router as admin_router

# Create FastAPI app
app = FastAPI(
    title="Gadgeto API",
    description="E-commerce API for Gadgeto store",
    version="1.0.0",
    docs_url="/docs" if config.settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if config.settings.ENVIRONMENT == "development" else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded media files
media_dir = config.settings.MEDIA_DIR
os.makedirs(media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_dir), name="media")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    # Database connection is lazy, no need to connect here
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    pass


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": config.settings.ENVIRONMENT}


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "name": "Gadgeto API",
        "version": "1.0.0",
        "docs": "/docs" if config.settings.ENVIRONMENT == "development" else None,
    }


# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request, exc):
    """Handle RuntimeError exceptions."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
