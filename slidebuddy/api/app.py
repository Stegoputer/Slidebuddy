"""FastAPI application — entry point for the SlideBuddy API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slidebuddy.config.defaults import DB_PATH
from slidebuddy.db.migrations import init_db

from .routers import chapters, generation, masters, projects, review, sections, settings, sources

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db(DB_PATH)
    logger.info("Database initialized at %s", DB_PATH)
    yield


app = FastAPI(
    title="SlideBuddy API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(sources.router, prefix="/api/projects", tags=["sources"])
app.include_router(chapters.router, prefix="/api/projects", tags=["chapters"])
app.include_router(sections.router, prefix="/api/projects", tags=["sections"])
app.include_router(generation.router, prefix="/api/projects", tags=["generation"])
app.include_router(review.router, prefix="/api/projects", tags=["review"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(masters.router, prefix="/api/masters", tags=["masters"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return the error detail.

    Without this, FastAPI returns a generic '500 Internal Server Error'
    with no detail — making debugging impossible from the frontend.
    """
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
