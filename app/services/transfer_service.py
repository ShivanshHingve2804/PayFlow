"""Transfer service — handles ACID money transfers between same-currency accounts."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.currency import validate_and_quantize_input
from app.exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
    InvalidOperationError,
    TransactionNotFoundError,
)
from app.models import Transaction
from app.schemas import TransferRequest
from app.services.locking import (
    commit_with_idempotency,
    compute_request_hash,
    enqueue_outbox_event,
    find_idempotent_transaction,
    lock_accounts_ordered,
    normalize_idempotency_key,
)


class TransferService:
    """Handles money transfers between accounts with the same currency."""

    @staticmethod
    def list_transfers(
        db: Session,
        *,
        limit: int = 100,
        offset: int = 0,
        transaction_type: str | None = "TRANSFER",
    ) -> list[Transaction]:
        query = db.query(Transaction)
        if transaction_type and transaction_type.upper() != "ALL":
            query = query.filter(Transaction.transaction_type == transaction_type.upper())
        return query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def create_transfer(db: Session, data: TransferRequest) -> Transaction:
        """Create an ACID transfer with ordered row locks, idempotency, and outbox."""
        if data.from_account_id == data.to_account_id:
            raise InvalidOperationError("Cannot transfer to the same account")

        key = normalize_idempotency_key(data.idempotency_key)
        req_hash = compute_request_hash(
            "TRANSFER",
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=Decimal(data.amount),
        )

        accounts = lock_accounts_ordered(db, data.from_account_id, data.to_account_id)
        existing = find_idempotent_transaction(db, key, req_hash)
        if existing is not None:
            return existing

        from_account = accounts[data.from_account_id]
        to_account = accounts[data.to_account_id]

        if from_account.currency != to_account.currency:
            raise CurrencyMismatchError(
                "Account currencies do not match. Use /api/v1/exchange for cross-currency transfers."
            )

        amount = validate_and_quantize_input(data.amount, from_account.currency)
        if from_account.balance < amount:
            raise InsufficientFundsError("Insufficient funds for transfer")

        from_account.balance -= amount
        to_account.balance += amount

        tx_id = str(uuid.uuid4())
        transaction = Transaction(
            id=tx_id,
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=amount,
            currency=from_account.currency,
            transaction_type="TRANSFER",
            idempotency_key=key,
            request_hash=req_hash,
            status="COMPLETED",
        )
        db.add(transaction)
        enqueue_outbox_event(
            db,
            aggregate_id=tx_id,
            event_type="TRANSFER_COMPLETED",
            payload={
                "transaction_id": tx_id,
                "from_account_id": data.from_account_id,
                "to_account_id": data.to_account_id,
                "amount": str(amount),
                "currency": from_account.currency,
                "idempotency_key": key,
            },
        )
        return commit_with_idempotency(db, transaction, key, req_hash)

    @staticmethod
    def get_transfer(db: Session, transfer_id: str) -> Transaction:
        """Get transaction details by ID."""
        transaction = db.query(Transaction).filter(Transaction.id == transfer_id).first()
        if not transaction:
            raise TransactionNotFoundError(f"Transfer {transfer_id} not found")
        return transaction
