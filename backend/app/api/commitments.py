"""Commitments endpoint — list all canonical commitments."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.commitment import Commitment
from app.schemas.commitment import CommitmentRead

router = APIRouter()


@router.get("/commitments", response_model=list[CommitmentRead])
def list_commitments(
    as_of_date: Optional[date] = Query(
        default=None,
        description="Reference date for computing overdue status (YYYY-MM-DD). "
        "Defaults to today.",
    ),
    db: Session = Depends(get_db),
):
    """Return all commitments with their source evidence links.

    The ``is_overdue`` flag is computed deterministically from the
    commitment's deadline and the supplied *as_of_date*.
    """
    reference = as_of_date or date.today()

    commitments = (
        db.query(Commitment)
        .options(joinedload(Commitment.source_links))
        .order_by(Commitment.created_at.desc())
        .all()
    )

    results = []
    for c in commitments:
        data = CommitmentRead.model_validate(c)
        data.is_overdue = c.is_overdue(reference)
        results.append(data)

    return results
