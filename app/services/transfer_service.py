import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import Account, Transaction
from app.schemas import TransferRequest
from app.exceptions import (AccountNotFoundError, InsufficientFundsError,
                            CurrencyMismatchError, InvalidOperationError)
from app.services.account_service import AccountService

class TransferService:
    @staticmethod
    def create_transfer(db: Session, data: TransferRequest) -> Transaction:
        """Create a transfer between accounts."""
        if data.from_account_id == data.to_account_id:
            raise InvalidOperationError("Cannot transfer to the same account")

        existing_tx = db.query(Transaction).filter(
            Transaction.idempotency_key == data.idempotency_key
        ).first()
        if existing_tx:
            return existing_tx

        from_account = AccountService.get_account(db, data.from_account_id)
        to_account = AccountService.get_account(db, data.to_account_id)

        if from_account.currency != to_account.currency:
            raise CurrencyMismatchError("Account currencies do not match. Use /exchange for cross-currency transfers.")

        sorted_ids = sorted([data.from_account_id, data.to_account_id])
        for aid in sorted_ids:
            try:
                db.execute(select(Account).where(Account.id == aid).with_for_update())
            except Exception:
                pass

        from_account = AccountService.get_account(db, data.from_account_id)
        to_account = AccountService.get_account(db, data.to_account_id)

        if from_account.balance < data.amount:
            raise InsufficientFundsError("Insufficient funds for transfer")

        from_account.balance -= data.amount
        to_account.balance += data.amount

        transaction = Transaction(
            id=str(uuid.uuid4()),
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=data.amount,
            currency=from_account.currency,
            transaction_type='TRANSFER',
            idempotency_key=data.idempotency_key,
            status='COMPLETED'
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def get_transfer(db: Session, transfer_id: str) -> Transaction:
        """Get transfer by ID."""
        transaction = db.query(Transaction).filter(Transaction.id == transfer_id).first()
        if not transaction:
            raise AccountNotFoundError(f"Transfer {transfer_id} not found")
        return transaction
