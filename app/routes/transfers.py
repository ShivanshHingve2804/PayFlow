"""Money transfer and ledger query routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction
from app.schemas import TransferRequest, TransferResponse
from app.services.transfer_service import TransferService

router = APIRouter(prefix="/api/v1/transfers", tags=["Transfers"])


@router.get("/", response_model=list[TransferResponse])
def list_transfers(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    transaction_type: str = Query("TRANSFER", pattern="^(TRANSFER|DEPOSIT|EXCHANGE|ALL)$"),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    """List transfers (or full ledger when `transaction_type=ALL`)."""
    return TransferService.list_transfers(
        db, limit=limit, offset=offset, transaction_type=transaction_type
    )


@router.post("/", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(data: TransferRequest, db: Session = Depends(get_db)) -> Transaction:
    """Create an ACID same-currency transfer."""
    return TransferService.create_transfer(db, data)


@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer(transfer_id: str, db: Session = Depends(get_db)) -> Transaction:
    """Get transfer by ID."""
    return TransferService.get_transfer(db, transfer_id)
