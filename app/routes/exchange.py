"""Multi-currency FX exchange routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction
from app.schemas import ExchangeRatesListResponse, ExchangeRequest, TransferResponse
from app.services.exchange_service import ExchangeService

router = APIRouter(prefix="/api/v1/exchange", tags=["Exchange"])


@router.get("/rates", response_model=ExchangeRatesListResponse)
def get_rates(db: Session = Depends(get_db)) -> ExchangeRatesListResponse:
    """Get all configured exchange rates across the 8 supported currencies."""
    rates = ExchangeService.get_rates(db)
    return ExchangeRatesListResponse(rates=rates)


@router.post("/", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_exchange(data: ExchangeRequest, db: Session = Depends(get_db)) -> Transaction:
    """Execute an atomic cross-currency exchange."""
    return ExchangeService.create_exchange(db, data)
