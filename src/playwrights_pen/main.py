"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import sessions_router, testcases_router
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown


app = FastAPI(
    title="PlaywrightsPen",
    description="Natural language automated testing service powered by Playwright MCP",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(testcases_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "PlaywrightsPen",
        "version": "0.1.0",
        "description": "剧作家之笔 - Natural language automated testing service",
        "docs": "/docs",
        "api_prefix": "/api/v1",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/config")
async def get_config():
    """Get current configuration (sanitized)."""
    return {
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "llm_api_key_set": bool(settings.llm_api_key),
        "browser_headless": settings.browser_headless,
        "default_confirmation_mode": settings.default_confirmation_mode.value,
        "data_dir": str(settings.data_dir),
    }


def run():
    """Run the application with uvicorn."""
    import uvicorn
    
    uvicorn.run(
        "playwrights_pen.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )


if __name__ == "__main__":
    run()
