"""Transfer service — handles money transfers between same-currency accounts."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    AccountNotFoundError,
    CurrencyMismatchError,
    InsufficientFundsError,
    InvalidOperationError,
)
from app.models import Account, Transaction
from app.schemas import TransferRequest


class TransferService:
    """Handles money transfers between accounts with the same currency."""

    @staticmethod
    def _lock_accounts(db: Session, *account_ids: str) -> None:
        """Lock accounts in sorted order to prevent deadlocks.

        Falls back gracefully on databases that don't support FOR UPDATE (e.g. SQLite).
        """
        for aid in sorted(account_ids):
            try:
                db.execute(
                    select(Account).where(Account.id == aid).with_for_update()
                )
            except Exception:
                # SQLite doesn't support FOR UPDATE — expire cache to ensure
                # the next query reads the latest committed state.
                db.expire_all()

    @staticmethod
    def create_transfer(db: Session, data: TransferRequest) -> Transaction:
        """Create a transfer between two same-currency accounts.

        Validates accounts exist, currencies match, and sufficient funds are
        available. Uses pessimistic locking to prevent race conditions.
        """
        if data.from_account_id == data.to_account_id:
            raise InvalidOperationError("Cannot transfer to the same account")

        # Idempotency check
        if data.idempotency_key:
            existing_tx = db.query(Transaction).filter(
                Transaction.idempotency_key == data.idempotency_key
            ).first()
            if existing_tx:
                return existing_tx

        # Validate accounts exist
        from_account = db.query(Account).filter(Account.id == data.from_account_id).first()
        if not from_account:
            raise AccountNotFoundError(f"Account {data.from_account_id} not found")

        to_account = db.query(Account).filter(Account.id == data.to_account_id).first()
        if not to_account:
            raise AccountNotFoundError(f"Account {data.to_account_id} not found")

        # Validate same currency
        if from_account.currency != to_account.currency:
            raise CurrencyMismatchError(
                "Account currencies do not match. Use /api/v1/exchange for cross-currency transfers."
            )

        # Lock accounts in consistent order to prevent deadlocks
        TransferService._lock_accounts(db, data.from_account_id, data.to_account_id)

        # Re-fetch after locking to get latest balances
        db.refresh(from_account)
        db.refresh(to_account)

        # Check sufficient funds
        if from_account.balance < data.amount:
            raise InsufficientFundsError("Insufficient funds for transfer")

        # Execute transfer
        from_account.balance -= data.amount
        to_account.balance += data.amount

        transaction = Transaction(
            id=str(uuid.uuid4()),
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=data.amount,
            currency=from_account.currency,
            transaction_type="TRANSFER",
            idempotency_key=data.idempotency_key,
            status="COMPLETED",
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def get_transfer(db: Session, transfer_id: str) -> Transaction:
        """Get transfer details by ID."""
        transaction = db.query(Transaction).filter(Transaction.id == transfer_id).first()
        if not transaction:
            raise AccountNotFoundError(f"Transfer {transfer_id} not found")
        return transaction
