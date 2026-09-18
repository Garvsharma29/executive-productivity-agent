"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return basic service health status."""
    return {
        "status": "healthy",
        "service": "executive-productivity-agent",
        "version": "0.1.0",
    }
