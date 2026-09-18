"""Daily Brief API endpoint."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent import DailyBriefResponse
from app.services.agent.daily_brief import BriefBuilder

router = APIRouter(tags=["brief"])


@router.get("/brief", response_model=DailyBriefResponse)
def get_daily_brief(
    as_of_date: Optional[date] = Query(
        default=None,
        description="Reference date for the daily brief (YYYY-MM-DD). Defaults to 2026-09-23 for assessment data.",
    ),
    db: Session = Depends(get_db),
):
    """Generate the Daily Executive Brief for Arjun Malhotra.

    Categorizes commitments into:
    - My Actions (open commitments owned by Arjun)
    - Waiting on Others (commitments where Arjun is counterpart)
    - Needs Attention (overdue, unclear ownership, or imminent deadline)
    - Completed deliverables
    - Scheduled Today (calendar context, NOT fake commitments)
    """
    builder = BriefBuilder(db)
    return builder.build_brief(as_of_date)
