"""Account service — handles account CRUD and race-safe deposits."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.currency import SUPPORTED_CURRENCIES, validate_and_quantize_input
from app.exceptions import AccountNotFoundError, InvalidOperationError
from app.models import Account, Transaction
from app.schemas import AccountCreate, BalanceResponse, DepositRequest
from app.services.locking import (
    commit_with_idempotency,
    compute_request_hash,
    enqueue_outbox_event,
    find_idempotent_transaction,
    lock_accounts_ordered,
    normalize_idempotency_key,
)


class AccountService:
    """Handles account creation, retrieval, and deposit operations."""

    @staticmethod
    def list_accounts(db: Session, *, limit: int = 100, offset: int = 0) -> list[Account]:
        return (
            db.query(Account).order_by(Account.created_at.desc()).offset(offset).limit(limit).all()
        )

    @staticmethod
    def create_account(db: Session, data: AccountCreate) -> Account:
        """Create a new account with validated minor-unit initial balance."""
        if data.currency not in SUPPORTED_CURRENCIES:
            raise InvalidOperationError(f"Unsupported currency: {data.currency}")

        initial = validate_and_quantize_input(data.initial_balance, data.currency)
        account = Account(
            id=str(uuid.uuid4()),
            owner_name=data.owner_name,
            currency=data.currency,
            initial_balance=initial,
            balance=initial,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def get_account(db: Session, account_id: str) -> Account:
        """Get account by ID. Raises AccountNotFoundError if not found."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    @staticmethod
    def get_balance(db: Session, account_id: str) -> BalanceResponse:
        """Get the current committed balance for an account."""
        account = AccountService.get_account(db, account_id)
        db.refresh(account)
        return BalanceResponse(
            account_id=account.id,
            currency=account.currency,
            balance=account.balance,
        )

    @staticmethod
    def deposit(db: Session, account_id: str, data: DepositRequest) -> Transaction:
        """Deposit money atomically under row lock with idempotency and outbox emission."""
        key = normalize_idempotency_key(data.idempotency_key)
        req_hash = compute_request_hash(
            "DEPOSIT", account_id=account_id, amount=Decimal(data.amount)
        )

        accounts = lock_accounts_ordered(db, account_id)
        existing = find_idempotent_transaction(db, key, req_hash)
        if existing is not None:
            return existing

        account = accounts[account_id]
        amount = validate_and_quantize_input(data.amount, account.currency)
        account.balance += amount

        tx_id = str(uuid.uuid4())
        transaction = Transaction(
            id=tx_id,
            to_account_id=account_id,
            amount=amount,
            currency=account.currency,
            transaction_type="DEPOSIT",
            idempotency_key=key,
            request_hash=req_hash,
            status="COMPLETED",
        )
        db.add(transaction)
        enqueue_outbox_event(
            db,
            aggregate_id=tx_id,
            event_type="DEPOSIT_COMPLETED",
            payload={
                "transaction_id": tx_id,
                "to_account_id": account_id,
                "amount": str(amount),
                "currency": account.currency,
                "idempotency_key": key,
            },
        )
        return commit_with_idempotency(db, transaction, key, req_hash)
