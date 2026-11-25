"""Account management and deposit routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Transaction
from app.schemas import (
    AccountCreate,
    AccountResponse,
    BalanceResponse,
    DepositRequest,
    TransferResponse,
)
from app.services.account_service import AccountService

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


@router.get("/", response_model=list[AccountResponse])
def list_accounts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[Account]:
    """List accounts with pagination."""
    return AccountService.list_accounts(db, limit=limit, offset=offset)


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, db: Session = Depends(get_db)) -> Account:
    """Create a new multi-currency account."""
    return AccountService.create_account(db, data)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: str, db: Session = Depends(get_db)) -> Account:
    """Get an account by ID."""
    return AccountService.get_account(db, account_id)


@router.get("/{account_id}/balance", response_model=BalanceResponse)
def get_balance(account_id: str, db: Session = Depends(get_db)) -> BalanceResponse:
    """Get current committed account balance."""
    return AccountService.get_balance(db, account_id)


@router.post(
    "/{account_id}/deposit",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def deposit(account_id: str, data: DepositRequest, db: Session = Depends(get_db)) -> Transaction:
    """Deposit funds into an account."""
    return AccountService.deposit(db, account_id, data)
