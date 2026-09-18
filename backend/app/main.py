"""
Executive Productivity Agent - Backend Application

FastAPI application with domain data model and database foundation.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.people import router as people_router
from app.api.commitments import router as commitments_router
from app.api.sources import router as sources_router

# Import models so all tables are registered with Base.metadata
import app.models  # noqa: F401
from app.core.database import create_tables


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create database tables on startup (assessment-appropriate strategy)."""
    create_tables()
    yield


app = FastAPI(
    title="Executive Productivity Agent",
    description="Converts messy executive inputs into a structured daily action brief.",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health_router, prefix="/api")
app.include_router(people_router, prefix="/api")
app.include_router(commitments_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
