import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import Account, Transaction
from app.schemas import AccountCreate, BalanceResponse, DepositRequest
from app.exceptions import AccountNotFoundError, DuplicateTransactionError, InvalidOperationError

SUPPORTED_CURRENCIES = {'USD', 'EUR', 'GBP', 'INR', 'JPY', 'AUD', 'CAD', 'CHF'}

class AccountService:
    @staticmethod
    def create_account(db: Session, data: AccountCreate) -> Account:
        """Create a new account."""
        if data.currency not in SUPPORTED_CURRENCIES:
            raise InvalidOperationError(f"Unsupported currency: {data.currency}")
        
        account = Account(
            id=str(uuid.uuid4()),
            owner_name=data.owner_name,
            currency=data.currency,
            balance=data.initial_balance
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def get_account(db: Session, account_id: str) -> Account:
        """Get account by ID."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    @staticmethod
    def get_balance(db: Session, account_id: str) -> BalanceResponse:
        """Get account balance."""
        account = AccountService.get_account(db, account_id)
        return BalanceResponse(
            account_id=account.id,
            currency=account.currency,
            balance=account.balance
        )

    @staticmethod
    def deposit(db: Session, account_id: str, data: DepositRequest) -> Transaction:
        """Deposit money into an account."""
        existing_tx = db.query(Transaction).filter(
            Transaction.idempotency_key == data.idempotency_key
        ).first()
        if existing_tx:
            return existing_tx

        try:
            db.execute(select(Account).where(Account.id == account_id).with_for_update())
        except Exception:
            pass

        account = AccountService.get_account(db, account_id)
        account.balance += data.amount

        transaction = Transaction(
            id=str(uuid.uuid4()),
            to_account_id=account_id,
            amount=data.amount,
            currency=account.currency,
            transaction_type='DEPOSIT',
            idempotency_key=data.idempotency_key,
            status='COMPLETED'
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction
