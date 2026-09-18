"""Executive Agent API endpoint for natural-language Q&A."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.services.agent.executive_agent import ExecutiveAgent

router = APIRouter(tags=["agent"])


@router.post("/agent/query", response_model=AgentQueryResponse)
def query_executive_agent(
    request: AgentQueryRequest,
    db: Session = Depends(get_db),
):
    """Answer natural-language questions grounded in canonical commitments and evidence.

    Supports queries such as:
    - "What did I promise Raghav?"
    - "What needs action today?"
    - "What is unclear?"
    - "What am I waiting on?"
    - "What's overdue?"
    """
    agent = ExecutiveAgent(db)
    return agent.answer_query(request.query, as_of_date=request.as_of_date)
