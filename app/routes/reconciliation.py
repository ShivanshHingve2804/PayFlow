"""Ledger reconciliation and outbox audit endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OutboxEvent, ProcessedEvent, ReconciliationReport
from app.schemas import ReconciliationReportResponse
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/api/v1/reconciliation", tags=["Reconciliation"])


@router.post(
    "/run",
    response_model=ReconciliationReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_reconciliation(
    report_date: str | None = Query(default=None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    db: Session = Depends(get_db),
) -> ReconciliationReport:
    """Run on-demand ledger balance conservation & outbox reconciliation."""
    return ReconciliationService.run_daily_reconciliation(db, report_date=report_date)


@router.get("/reports", response_model=list[ReconciliationReportResponse])
def list_reconciliation_reports(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ReconciliationReport]:
    """List recent daily reconciliation audit reports."""
    return ReconciliationService.list_reports(db, limit=limit)


@router.get("/outbox")
def get_outbox_stats(db: Session = Depends(get_db)) -> dict[str, int]:
    """Inspect transactional outbox and deduplicated Kafka consumer progress."""
    pending = (
        db.query(func.count(OutboxEvent.id)).filter(OutboxEvent.status == "PENDING").scalar() or 0
    )
    published = (
        db.query(func.count(OutboxEvent.id)).filter(OutboxEvent.status == "PUBLISHED").scalar() or 0
    )
    processed = db.query(func.count(ProcessedEvent.event_id)).scalar() or 0
    return {
        "outbox_pending": int(pending),
        "outbox_published": int(published),
        "consumer_processed": int(processed),
    }
