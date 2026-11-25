"""Shared pessimistic row-locking, idempotency fingerprinting, and outbox helpers."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import (
    AccountNotFoundError,
    DuplicateTransactionError,
    InvalidOperationError,
)
from app.models import Account, OutboxEvent, Transaction


def normalize_idempotency_key(key: str | None) -> str | None:
    """Ensure idempotency keys are either `None` or non-empty trimmed strings."""
    if key is None:
        return None
    cleaned = key.strip()
    if not cleaned:
        raise InvalidOperationError("idempotency_key cannot be blank")
    return cleaned


def compute_request_hash(operation: str, **fields: Any) -> str:
    """Create a deterministic SHA-256 fingerprint for idempotency payload matching."""
    normalized: dict[str, Any] = {"operation": operation}
    for k, v in sorted(fields.items()):
        if isinstance(v, Decimal):
            normalized[k] = f"{v.quantize(Decimal('0.01'))}"
        else:
            normalized[k] = v
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def find_idempotent_transaction(
    db: Session, idempotency_key: str | None, request_hash: str
) -> Transaction | None:
    """Return existing transaction if key+payload match, or raise 409 on payload mismatch."""
    if idempotency_key is None:
        return None
    existing = db.query(Transaction).filter(Transaction.idempotency_key == idempotency_key).first()
    if existing is None:
        return None
    if existing.request_hash is not None and existing.request_hash != request_hash:
        raise DuplicateTransactionError(
            "Idempotency key already used for a different transaction payload"
        )
    return existing


def lock_accounts_ordered(db: Session, *account_ids: str) -> dict[str, Account]:
    """Acquire row locks in sorted account-ID order to prevent AB-BA deadlocks."""
    bind = db.get_bind()
    supports_for_update = bind is not None and bind.dialect.name != "sqlite"

    # Expire cached objects so subsequent reads reflect committed balances on all dialects.
    db.expire_all()
    locked: dict[str, Account] = {}
    for aid in sorted(set(account_ids)):
        stmt = select(Account).where(Account.id == aid)
        if supports_for_update:
            stmt = stmt.with_for_update()
        account = db.execute(stmt).scalar_one_or_none()
        if account is None:
            raise AccountNotFoundError(f"Account {aid} not found")
        locked[aid] = account
    return locked


def enqueue_outbox_event(
    db: Session,
    *,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Stage a post-commit Kafka outbox event inside the active database transaction."""
    event = OutboxEvent(
        aggregate_type="Transaction",
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=json.dumps(payload, default=str, sort_keys=True),
        status="PENDING",
    )
    db.add(event)
    return event


def commit_with_idempotency(
    db: Session,
    transaction: Transaction,
    idempotency_key: str | None,
    request_hash: str,
) -> Transaction:
    """Commit transaction + outbox atomically; resolve concurrent idempotency races cleanly."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key is not None:
            existing = (
                db.query(Transaction).filter(Transaction.idempotency_key == idempotency_key).first()
            )
            if existing is not None:
                if existing.request_hash is not None and existing.request_hash != request_hash:
                    raise DuplicateTransactionError(
                        "Idempotency key already used for a different transaction payload"
                    ) from exc
                return existing
        raise exc
    db.refresh(transaction)
    return transaction
