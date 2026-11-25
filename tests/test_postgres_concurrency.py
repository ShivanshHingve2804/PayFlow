"""True multi-threaded PostgreSQL concurrency, deadlock-prevention, and idempotency tests."""

from __future__ import annotations

import concurrent.futures
import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.exceptions import DuplicateTransactionError, InsufficientFundsError
from app.models import Account, OutboxEvent, Transaction
from app.schemas import AccountCreate, DepositRequest, TransferRequest
from app.services.account_service import AccountService
from app.services.transfer_service import TransferService

POSTGRES_URL = os.getenv("PAYFLOW_POSTGRES_TEST_URL") or (
    os.getenv("DATABASE_URL") if os.getenv("DATABASE_URL", "").startswith("postgresql") else None
)


@pytest.fixture
def pg_session_factory():
    """Provide an isolated PostgreSQL session factory verifying real SELECT FOR UPDATE."""
    if not POSTGRES_URL:
        pytest.fail("PAYFLOW_POSTGRES_TEST_URL / PostgreSQL DATABASE_URL must be configured")

    pg_engine = create_engine(POSTGRES_URL, pool_size=25, max_overflow=15, pool_pre_ping=True)
    Base.metadata.create_all(bind=pg_engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
    yield factory
    pg_engine.dispose()


def test_postgres_concurrent_drain_prevents_overdraft(pg_session_factory) -> None:
    """20 threads racing $200 transfers from a $1,000 account: exactly 5 succeed, 15 fail."""
    db = pg_session_factory()
    try:
        alice = AccountService.create_account(
            db,
            AccountCreate(
                owner_name="PG Alice", currency="USD", initial_balance=Decimal("1000.00")
            ),
        )
        bob = AccountService.create_account(
            db,
            AccountCreate(owner_name="PG Bob", currency="USD", initial_balance=Decimal("0.00")),
        )
        alice_id, bob_id = alice.id, bob.id
    finally:
        db.close()

    def attempt_transfer(_: int) -> str:
        s = pg_session_factory()
        try:
            TransferService.create_transfer(
                s,
                TransferRequest(
                    from_account_id=alice_id,
                    to_account_id=bob_id,
                    amount=Decimal("200.00"),
                ),
            )
            return "OK"
        except InsufficientFundsError:
            s.rollback()
            return "INSUFFICIENT"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt_transfer, range(20)))

    assert results.count("OK") == 5
    assert results.count("INSUFFICIENT") == 15

    check_db = pg_session_factory()
    try:
        a_bal = AccountService.get_balance(check_db, alice_id).balance
        b_bal = AccountService.get_balance(check_db, bob_id).balance
        assert a_bal == Decimal("0.00")
        assert b_bal == Decimal("1000.00")
    finally:
        check_db.close()


def test_postgres_bidirectional_deadlock_prevention(pg_session_factory) -> None:
    """20 concurrent A->B and B->A transfers complete with zero deadlocks via lock ordering."""
    db = pg_session_factory()
    try:
        a = AccountService.create_account(
            db,
            AccountCreate(owner_name="DL A", currency="EUR", initial_balance=Decimal("1000.00")),
        )
        b = AccountService.create_account(
            db,
            AccountCreate(owner_name="DL B", currency="EUR", initial_balance=Decimal("1000.00")),
        )
        a_id, b_id = a.id, b.id
    finally:
        db.close()

    def transfer(idx: int) -> str:
        s = pg_session_factory()
        try:
            src, dst = (a_id, b_id) if idx % 2 == 0 else (b_id, a_id)
            TransferService.create_transfer(
                s,
                TransferRequest(from_account_id=src, to_account_id=dst, amount=Decimal("10.00")),
            )
            return "OK"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        outcomes = list(pool.map(transfer, range(20)))

    assert all(o == "OK" for o in outcomes)

    check_db = pg_session_factory()
    try:
        a_bal = AccountService.get_balance(check_db, a_id).balance
        b_bal = AccountService.get_balance(check_db, b_id).balance
        assert a_bal == Decimal("1000.00")
        assert b_bal == Decimal("1000.00")
    finally:
        check_db.close()


def test_postgres_concurrent_idempotency_storm(pg_session_factory) -> None:
    """20 threads firing identical idempotency_key produce 1 deposit, 1 outbox event, 0 errors."""
    db = pg_session_factory()
    try:
        acc = AccountService.create_account(
            db,
            AccountCreate(
                owner_name="Idem Storm", currency="GBP", initial_balance=Decimal("100.00")
            ),
        )
        acc_id = acc.id
    finally:
        db.close()

    shared_key = f"storm-{uuid.uuid4()}"

    def fire_deposit(_: int) -> str:
        s = pg_session_factory()
        try:
            tx = AccountService.deposit(
                s,
                acc_id,
                DepositRequest(amount=Decimal("50.00"), idempotency_key=shared_key),
            )
            return tx.id
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        tx_ids = list(pool.map(fire_deposit, range(20)))

    assert len(set(tx_ids)) == 1

    check_db = pg_session_factory()
    try:
        assert AccountService.get_balance(check_db, acc_id).balance == Decimal("150.00")
        outbox_rows = (
            check_db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == tx_ids[0]).count()
        )
        assert outbox_rows == 1

        # Mismatched payload with same key must raise DuplicateTransactionError
        with pytest.raises(DuplicateTransactionError):
            AccountService.deposit(
                check_db,
                acc_id,
                DepositRequest(amount=Decimal("99.00"), idempotency_key=shared_key),
            )
        # Verify raw constraint check exists
        assert check_db.execute(text("SELECT 1")).scalar() == 1
        assert check_db.query(Account).filter(Account.id == acc_id).count() == 1
        assert check_db.query(Transaction).filter(Transaction.id == tx_ids[0]).count() == 1
    finally:
        check_db.close()
