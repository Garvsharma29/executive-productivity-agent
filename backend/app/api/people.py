"""People endpoint — list all known persons."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.person import Person
from app.schemas.person import PersonRead

router = APIRouter()


@router.get("/people", response_model=list[PersonRead])
def list_people(db: Session = Depends(get_db)):
    """Return all known persons from the assessment data."""
    return db.query(Person).order_by(Person.name).all()
