# backend/main.py - FastAPI Application Entry Point

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.api.routes import workflow_routes
from backend.config.settings import settings
from backend.config.logging_config import setup_logging
from backend.services.qdrant_manager import QdrantManager
from backend.services.ollama_manager import OllamaManager
from backend.services.git_manager import GitManager

# Setup structured logging
setup_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    FastAPI lifespan context manager for startup/shutdown
    
    Initializes connections on startup, cleans up on shutdown
    """
    # Startup
    logger.info(
        "startup_begin",
        environment=settings.ENVIRONMENT,
        log_level=settings.LOG_LEVEL
    )
    
    try:
        # Initialize Qdrant connection
        qdrant_mgr = QdrantManager(settings.QDRANT_URL)
        await qdrant_mgr.connect()
        logger.info("qdrant_connected", url=settings.QDRANT_URL)
        
        # Initialize Ollama connection
        ollama_mgr = OllamaManager(settings.OLLAMA_BASE_URL)
        await ollama_mgr.verify_connection()
        logger.info("ollama_connected", url=settings.OLLAMA_BASE_URL)
        
        # Store in app state
        app.state.qdrant = qdrant_mgr
        app.state.ollama = ollama_mgr
        
        logger.info("startup_complete")
    
    except Exception as e:
        logger.error("startup_failed", error=str(e), exc_info=True)
        sys.exit(1)
    
    yield
    
    # Shutdown
    logger.info("shutdown_begin")
    try:
        # Cleanup connections
        if hasattr(app.state, "qdrant"):
            await app.state.qdrant.disconnect()
        logger.info("shutdown_complete")
    except Exception as e:
        logger.error("shutdown_error", error=str(e), exc_info=True)


# Create FastAPI app
app = FastAPI(
    title="Agentic IDE Backend",
    description="LLM-orchestrated multi-agent code generation system",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(workflow_routes.router, prefix="/api", tags=["workflow"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/debug/vram")
async def debug_vram():
    """Debug endpoint: GPU VRAM usage"""
    try:
        # Get Ollama VRAM info via API
        vram_info = await app.state.ollama.get_vram_info()
        return vram_info
    except Exception as e:
        logger.error("vram_query_failed", error=str(e))
        return {"error": str(e)}


@app.get("/debug/metrics")
async def debug_metrics():
    """Debug endpoint: Agent execution metrics"""
    # TODO: Implement metrics collection
    return {
        "agents": {
            "code_generation": {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.ENVIRONMENT == "development",
        log_config=None,  # Use structlog
    )
