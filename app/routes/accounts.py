from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import AccountCreate, AccountResponse, BalanceResponse, DepositRequest, TransferResponse
from app.services.account_service import AccountService

router = APIRouter(prefix='/api/v1/accounts', tags=['Accounts'])

@router.post('/', response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    """Create a new account."""
    return AccountService.create_account(db, data)

@router.get('/{account_id}', response_model=AccountResponse)
def get_account(account_id: str, db: Session = Depends(get_db)):
    """Get an account by ID."""
    return AccountService.get_account(db, account_id)

@router.get('/{account_id}/balance', response_model=BalanceResponse)
def get_balance(account_id: str, db: Session = Depends(get_db)):
    """Get account balance."""
    return AccountService.get_balance(db, account_id)

@router.post('/{account_id}/deposit', response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def deposit(account_id: str, data: DepositRequest, db: Session = Depends(get_db)):
    """Deposit money into an account."""
    return AccountService.deposit(db, account_id, data)
