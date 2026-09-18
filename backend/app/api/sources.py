"""Sources endpoint — retrieve a specific source by ID."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.source import Source
from app.schemas.source import SourceRead

router = APIRouter()


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return a single Source by its ID.

    Useful for tracing a commitment back to its original evidence.
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source
