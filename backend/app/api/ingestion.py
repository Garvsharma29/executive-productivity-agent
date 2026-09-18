"""API router for Data Pack ingestion."""

from typing import Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.ingestion.ingestion_service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class IngestionRequest(BaseModel):
    data_pack_path: Optional[str] = None


@router.post("/data-pack", response_model=dict[str, Any])
def trigger_data_pack_ingestion(
    payload: Optional[IngestionRequest] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Deterministically ingest the Data Pack into PostgreSQL/SQLAlchemy."""
    path = payload.data_pack_path if payload else None
    try:
        service = IngestionService(db=db, data_pack_path=path)
        return service.run()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
