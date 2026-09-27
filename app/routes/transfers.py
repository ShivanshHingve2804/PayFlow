from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import TransferRequest, TransferResponse
from app.services.transfer_service import TransferService

router = APIRouter(prefix='/api/v1/transfers', tags=['Transfers'])

@router.get('/', response_model=list[TransferResponse])
def list_transfers(db: Session = Depends(get_db)):
    """List all transfers."""
    return TransferService.list_transfers(db)

@router.post('/', response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(data: TransferRequest, db: Session = Depends(get_db)):
    """Create a transfer."""
    return TransferService.create_transfer(db, data)

@router.get('/{transfer_id}', response_model=TransferResponse)
def get_transfer(transfer_id: str, db: Session = Depends(get_db)):
    """Get transfer by ID."""
    return TransferService.get_transfer(db, transfer_id)
