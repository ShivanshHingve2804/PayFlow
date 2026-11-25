"""Currency exchange service — 8-currency FX matrix, minor-unit rounding, and ACID swaps."""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.currency import (
    USD_BASE_RATES,
    quantize_converted,
    validate_and_quantize_input,
)
from app.exceptions import (
    ExchangeRateNotFoundError,
    InsufficientFundsError,
    InvalidOperationError,
)
from app.models import ExchangeRate, Transaction
from app.schemas import ExchangeRateResponse, ExchangeRequest
from app.services.locking import (
    commit_with_idempotency,
    compute_request_hash,
    enqueue_outbox_event,
    find_idempotent_transaction,
    lock_accounts_ordered,
    normalize_idempotency_key,
)


class ExchangeService:
    """Handles FX rate management and multi-currency exchanges."""

    @staticmethod
    def seed_default_rates(db: Session) -> None:
        """Seed complete 56-pair FX matrix across all 8 supported currencies."""
        if db.query(ExchangeRate).count() > 0:
            return

        currencies = sorted(USD_BASE_RATES.keys())
        for from_curr in currencies:
            for to_curr in currencies:
                if from_curr == to_curr:
                    continue
                cross_rate = (USD_BASE_RATES[to_curr] / USD_BASE_RATES[from_curr]).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                )
                db.add(
                    ExchangeRate(
                        id=str(uuid.uuid4()),
                        from_currency=from_curr,
                        to_currency=to_curr,
                        rate=cross_rate,
                    )
                )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    @staticmethod
    def get_rates(db: Session) -> list[ExchangeRateResponse]:
        """Get all configured FX rates."""
        rates = (
            db.query(ExchangeRate)
            .order_by(ExchangeRate.from_currency, ExchangeRate.to_currency)
            .all()
        )
        return [
            ExchangeRateResponse(
                from_currency=r.from_currency,
                to_currency=r.to_currency,
                rate=r.rate,
            )
            for r in rates
        ]

    @staticmethod
    def get_rate(db: Session, from_currency: str, to_currency: str) -> Decimal:
        """Get exchange rate for a currency pair."""
        if from_currency == to_currency:
            return Decimal("1.000000")

        rate_obj = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.from_currency == from_currency,
                ExchangeRate.to_currency == to_currency,
            )
            .first()
        )
        if not rate_obj:
            raise ExchangeRateNotFoundError(
                f"Exchange rate from {from_currency} to {to_currency} not found"
            )
        return rate_obj.rate

    @staticmethod
    def create_exchange(db: Session, data: ExchangeRequest) -> Transaction:
        """Execute an atomic cross-currency exchange with full FX audit metadata."""
        if data.from_account_id == data.to_account_id:
            raise InvalidOperationError("Use /transfers for same-currency transfers")

        key = normalize_idempotency_key(data.idempotency_key)
        req_hash = compute_request_hash(
            "EXCHANGE",
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

        if from_account.currency == to_account.currency:
            raise InvalidOperationError("Use /transfers for same-currency transfers")

        amount = validate_and_quantize_input(data.amount, from_account.currency)
        rate = ExchangeService.get_rate(db, from_account.currency, to_account.currency)
        converted_amount = quantize_converted(amount * rate, to_account.currency)
        if converted_amount <= Decimal("0.00"):
            raise InvalidOperationError(f"Converted amount rounds to zero in {to_account.currency}")

        if from_account.balance < amount:
            raise InsufficientFundsError("Insufficient funds for exchange")

        from_account.balance -= amount
        to_account.balance += converted_amount

        tx_id = str(uuid.uuid4())
        transaction = Transaction(
            id=tx_id,
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=amount,
            currency=from_account.currency,
            target_amount=converted_amount,
            target_currency=to_account.currency,
            exchange_rate=rate,
            transaction_type="EXCHANGE",
            idempotency_key=key,
            request_hash=req_hash,
            status="COMPLETED",
        )
        db.add(transaction)
        enqueue_outbox_event(
            db,
            aggregate_id=tx_id,
            event_type="EXCHANGE_COMPLETED",
            payload={
                "transaction_id": tx_id,
                "from_account_id": data.from_account_id,
                "to_account_id": data.to_account_id,
                "amount": str(amount),
                "currency": from_account.currency,
                "target_amount": str(converted_amount),
                "target_currency": to_account.currency,
                "exchange_rate": str(rate),
                "idempotency_key": key,
            },
        )
        return commit_with_idempotency(db, transaction, key, req_hash)
